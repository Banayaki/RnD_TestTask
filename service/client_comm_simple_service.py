import pandas as pd
from loguru import logger

from model import Client, CommType, Prediction
from service.client_comm_service import ClientCommService
from settings import Settings, settings


class ClientCommSimpleService(ClientCommService):
    def score(
        self,
        profile: Client,
        comm_type: CommType,
        comm_history: pd.DataFrame,
        clients_db: pd.DataFrame,
        comm_db: pd.DataFrame,
        runtime_settings: Settings | None = None,
        **kwargs
    ) -> Prediction:
        active_settings = runtime_settings or settings

        comm_history_filtered: pd.DataFrame = comm_history[
            comm_history["comm_type"] == comm_type.value
        ]  # pyright: ignore[reportAssignmentType]
        if not {"age_bin", "salary_bin", "delinq_bin"}.issubset(clients_db.columns):
            self._enrich_client_features(profile, clients_db)

        # 1. Находим похожих клиентов: фильтруем справочники.
        similar_clients = self._find_similar_clients(profile, clients_db)
        _, n_sim, p_sim = self._filter_similar_clients_comms(
            similar_clients, comm_db, comm_type
        )
        # 2. Проверить историю проверяемого клиента
        n_own, p_own = self._calc_success_rate(comm_history_filtered)
        # Условие из ТЗ.
        if n_own == 0:
            p_own = p_sim
        # 3. Считаем усталость клиента
        fatigue_coefficient = self._calc_fatigue(
            comm_history_filtered,
            active_settings,
            positive_coefficient=kwargs.get(
                "fatigue_coefficient_positive",
                active_settings.fatigue_coefficient_positive,
            ),
            negative_coefficient=kwargs.get(
                "fatigue_coefficient_negative",
                active_settings.fatigue_coefficient_negative,
            ),
            unsuccessful_comms_threshold=kwargs.get(
                "unsuccessful_comms_threshold",
                active_settings.unsuccessful_comms_threshold,
            ),
        )
        # 4. Вычисляем итоговый скор
        score = self._calc_score(
            n_own,
            p_own,
            n_sim,
            p_sim,
            fatigue_coefficient,
            own_history_min_count=kwargs.get(
                "own_history_min_count", active_settings.own_history_min_count
            ),
            sim_coef=kwargs.get("sim_coef", active_settings.sim_coef),
            own_coef=kwargs.get("own_coef", active_settings.own_coef),
        )
        # 5. Собираем результат
        pred = Prediction(
            p_sim=p_sim,
            n_sim=n_sim,
            p_own=p_own,
            n_own=n_own,
            fatigue=fatigue_coefficient,
            score=score,
            age_bin=profile.age_bin,
            salary_bin=profile.salary_bin,
            delinq_bin=profile.delinq_bin,
            pin=profile.client_pin,
            comm_type=comm_type,
        )
        return pred

    def _calc_score(
        self,
        n_own: int,
        p_own: float,
        n_sim: int,
        p_sim: float,
        fatigue_coefficient: float,
        own_history_min_count: int = 3,
        sim_coef: float = 0.7,
        own_coef: float = 0.3,
    ) -> float:
        """
        Вычисляет итоговый скор по следующему правилу:
        - При `n_own >= own_history_min_count`:
            `P_raw = sim_coef * p_sim + own_coef * p_own`
        - При `n_own < own_history_min_count`:
            `P_raw = p_sim`
        - `P = P_raw * fatigue_coefficient`.

        Стандартные значения: `own_history_min_count=3`, `sim_coef=0.7`, `own_coef=0.3`.
        Приоритет оценки при стандартных (0.7, 0.3) отдается похожим клиентам.
        """
        if n_own >= own_history_min_count:
            score = sim_coef * p_sim + own_coef * p_own
        else:  # elif n_own < 3:
            score = p_sim
        return score * fatigue_coefficient

    def _calc_fatigue(
        self,
        comm_history: pd.DataFrame,
        runtime_settings: Settings,
        positive_coefficient: float = 1.0,
        negative_coefficient: float = 0.7,
        unsuccessful_comms_threshold: int = 1
    ) -> float:
        """
        Вычисляет степень усталости клиента по определенному диапазону дат, заданных в настройках.
        Подразумевает что `comm_date` сконвертирован в datetime.
        Допускает некорректные даты - игнорируются.
        """
        if not pd.api.types.is_datetime64_any_dtype(comm_history["comm_date"]):
            logger.error(
                "comm_date column is not of type datetime. Sanitize before use."
            )
            raise ValueError(
                "comm_date column is not of type datetime. Sanitize before use."
            )
        filtered_comm_history = comm_history[
            (comm_history["comm_date"] >= runtime_settings.fatigue_start_date)
            & (comm_history["comm_date"] <= runtime_settings.fatigue_end_date)
        ]
        # Если не было коммуникаций
        if filtered_comm_history.empty:
            return positive_coefficient
        n_success = filtered_comm_history["success"].sum()
        # Если хотя бы одна коммуникация не успешна
        if len(filtered_comm_history) - n_success >= unsuccessful_comms_threshold:
            return negative_coefficient
        return positive_coefficient

    def _find_similar_clients(
        self,
        profile: Client,
        clients_db: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Находит похожих клиентов.
        Похожий клиент совпадает по всем трём полям: возрастной корзине, зарплатному и просроченному бинам.
        """
        if not {"age_bin", "salary_bin", "delinq_bin"}.issubset(clients_db.columns):
            logger.warning("Client features not enriched, enriching now")
            self._enrich_client_features(profile, clients_db)

        similar_clients = clients_db.query(
            "age_bin == @profile.age_bin and "
            "salary_bin == @profile.salary_bin and "
            "delinq_bin == @profile.delinq_bin and "
            "client_pin != @profile.client_pin"
        )
        return similar_clients

    def _filter_similar_clients_comms(
        self,
        similar_clients: pd.DataFrame,
        comm_db: pd.DataFrame,
        comm_type: CommType,
    ) -> tuple[pd.DataFrame, int, float]:
        """
        Выполняет фильтрацию базы знаний о коммуникациях по типу коммуникации и похожим клиентам.
        Заодно вычисляет количество похожих и долю успешных коммуникаций.
        """
        filtered_comms: pd.DataFrame = comm_db[comm_db["comm_type"] == comm_type.value]  # pyright: ignore[reportAssignmentType]
        filtered_comms = filtered_comms[
            filtered_comms["client_pin"].isin(similar_clients["client_pin"])
        ]  # pyright: ignore[reportAssignmentType]

        n_sim, p_sim = self._calc_success_rate(filtered_comms)
        return filtered_comms, n_sim, p_sim

    def _calc_success_rate(self, comms_data: pd.DataFrame) -> tuple[int, float]:
        """
        Вычисляет количество успешных коммуникаций и их долю.
        """
        n_success = comms_data["success"].sum()
        n_total = len(comms_data)
        p_success = n_success / n_total if n_total > 0 else 0.0
        return n_total, p_success

    def _enrich_client_features(
        self,
        profile: Client,
        clients_db: pd.DataFrame,
    ):
        """
        Добавляет вычисляемые признаки клиента: age_bin, salary_bin, delinq_bin.
        Операция не создает новую таблицу, выполняется inplace.
        """
        clients_db["age_bin"] = clients_db["age_years"].apply(Client.calc_age_bin)
        clients_db["salary_bin"] = clients_db["salary_flag"].apply(
            Client.calc_salary_bin
        )
        clients_db["delinq_bin"] = clients_db["delinquency_cur_flag"].apply(
            Client.calc_delinq_bin
        )
