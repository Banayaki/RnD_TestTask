import inspect
from dataclasses import fields
from datetime import datetime
from io import StringIO
from profile import run

import pandas as pd
import streamlit as st
from loguru import logger

from model import Client, CommType, Communication, Prediction
from service import ClientCommService
from settings import Settings, settings
from tools import CsvSanitizationResult, CsvSanitizer
from ui.styles import APP_CSS

COMM_TYPE_LABELS = {
    CommType.PUSH_CASHBACK: "Пуш · кэшбэк",
    CommType.SMS_CASHBACK: "SMS · кэшбэк",
    CommType.EMAIL_CASHBACK: "Email · кэшбэк",
    CommType.PUSH_CREDIT: "Пуш · кредитка или лимит",
    CommType.SMS_REFINANCE: "SMS · рефинансирование",
    CommType.PUSH_SERVICE: "Пуш · сервисное уведомление",
    CommType.CALL_COLLECT: "Звонок · задолженность",
}


class StreamlitApp:
    def __init__(
        self, client_comm_service: ClientCommService, csv_sanitizer: CsvSanitizer
    ) -> None:
        self._client_comm_service = client_comm_service
        self._csv_sanitizer = csv_sanitizer

    def _load_demo_clients(self, clients_path: str) -> CsvSanitizationResult:
        result = self._csv_sanitizer.read_and_sanitize(clients_path, Client)
        logger.info(f"Loaded demo clients: {len(result.data)} rows")
        return result

    def _load_demo_comms(self, communications_path: str) -> CsvSanitizationResult:
        result = self._csv_sanitizer.read_and_sanitize(communications_path)
        logger.info(f"Loaded demo comms: {len(result.data)} rows")
        return result

    @staticmethod
    def _render_sanitization_issues(result: CsvSanitizationResult) -> bool:
        for warning in result.warnings:
            st.warning(str(warning))
        for error in result.errors:
            # st.exception(error)
            st.error(error)
        return bool(result.errors)

    def _render_calculation(self, prediction: Prediction) -> None:
        with st.container(border=True):
            st.subheader("Расшифровка расчёта")
            st.caption(
                f"PIN: {prediction.pin} · тип: {COMM_TYPE_LABELS[prediction.comm_type]}"
            )

            similar_column, own_column, outcome_column = st.columns(3)
            with similar_column:
                st.markdown("**Похожие клиенты**")
                st.metric(
                    "p_sim",
                    f"{prediction.p_sim:.1%}",
                    help="Доля удачных коммуникаций с похожими клиентами",
                )
                st.metric(
                    "n_sim",
                    prediction.n_sim,
                    help="Число коммуникаций с похожими клиентами",
                )
            with own_column:
                st.markdown("**Личная история**")
                st.metric(
                    "p_own",
                    f"{prediction.p_own:.1%}",
                    help="Доля удачных коммуникаций выбранного клиента",
                )
                st.metric(
                    "n_own",
                    prediction.n_own,
                    help="Число коммуникаций с выбранным клиентом",
                )
            with outcome_column:
                st.markdown("**Итог**")
                st.metric(
                    "fatigue",
                    f"{prediction.fatigue:.1f}",
                    help="Коэффициент усталости клиента от коммуникаций",
                )
                st.metric(
                    "P",
                    f"{prediction.score:.1%}",
                    help="Вероятность успешной коммуникации",
                )
                st.metric(
                    "Вердикт", prediction.verdict, help=Prediction.verdict.__doc__
                )

            st.markdown("**Признаки похожести**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "age_bucket": prediction.age_bin,
                            "salary_bin": prediction.salary_bin,
                            "delinq_bin": prediction.delinq_bin,
                        }
                    ]
                ),
                width="stretch",
                hide_index=True,
            )

    @staticmethod
    def _render_recent_communications(
        comm_history: pd.DataFrame, widget_key: str
    ) -> None:
        st.subheader("Последние коммуникации")
        records_limit = st.selectbox(
            "Количество записей",
            options=(5, 10, 25, 50, 100),
            key=f"{widget_key}_recent_comms_limit",
        )
        latest_comms = comm_history.sort_values("comm_date", ascending=False).head(
            records_limit
        )
        st.caption(f"Показано: {len(latest_comms)} из {len(comm_history)}")
        st.dataframe(latest_comms, width="stretch", hide_index=True)

    @staticmethod
    def _build_client(profile: pd.Series) -> Client:
        return Client(**{field.name: profile[field.name] for field in fields(Client)})

    @staticmethod
    def _render_settings() -> Settings:
        runtime_settings = st.session_state.setdefault("runtime_settings", settings)
        with st.expander("Настройки", icon=":material/tune:"):
            with st.form("runtime_settings_form", border=False):
                clients_path = st.text_input(
                    "Путь к CSV клиентов", value=runtime_settings.clients_path
                )
                communications_path = st.text_input(
                    "Путь к CSV коммуникаций",
                    value=runtime_settings.communications_path,
                )
                start_column, end_column = st.columns(2)
                fatigue_start_date = start_column.date_input(
                    "Начало окна усталости",
                    value=runtime_settings.fatigue_start_date,
                    format="DD.MM.YYYY",
                )
                fatigue_end_date = end_column.date_input(
                    "Конец окна усталости",
                    value=runtime_settings.fatigue_end_date,
                    format="DD.MM.YYYY",
                )
                manual_mode_filter_history_by_pin = st.checkbox(
                    "Фильтровать историю коммуникаций по пину",
                    value=runtime_settings.manual_mode_filter_history_by_pin,
                )
                st.markdown("**Константы расчёта**")
                first_constant_column, second_constant_column = st.columns(2)
                own_history_min_count = first_constant_column.number_input(
                    "own_history_min_count",
                    min_value=0,
                    value=runtime_settings.own_history_min_count,
                    step=1,
                    help="Минимальное количество коммуникаций в истории для учета в оценке",
                )
                sim_coef = second_constant_column.number_input(
                    "sim_coef",
                    min_value=0.0,
                    value=runtime_settings.sim_coef,
                    step=0.1,
                    help="Коэффициент оценки похожих коммуникаций (0.7)",
                )
                own_coef = first_constant_column.number_input(
                    "own_coef",
                    min_value=0.0,
                    value=runtime_settings.own_coef,
                    step=0.1,
                    help="Коэффициент оценки собственных коммуникаций (0.3)",
                )
                fatigue_coefficient_positive = second_constant_column.number_input(
                    "fatigue_coefficient_positive",
                    min_value=0.0,
                    value=runtime_settings.fatigue_coefficient_positive,
                    step=0.1,
                    help="Коэффициент положительной усталости (1.0)",
                )
                fatigue_coefficient_negative = first_constant_column.number_input(
                    "fatigue_coefficient_negative",
                    min_value=0.0,
                    value=runtime_settings.fatigue_coefficient_negative,
                    step=0.1,
                    help="Коэффициент отрицательной усталости, используется когда превышается " +
                        "`unsuccessful_comms_threshold` за определенный временной интервал (0.7)",
                )
                unsuccessful_comms_threshold = second_constant_column.number_input(
                    "unsuccessful_comms_threshold",
                    min_value=0,
                    value=runtime_settings.unsuccessful_comms_threshold,
                    step=1,
                    help="Чисто неуспешных коммуникаций превышение которого означает усталость клиента (1)",
                )

                submitted = st.form_submit_button(
                    "Применить настройки", type="primary", width="stretch"
                )

            if submitted:
                runtime_settings = Settings(
                    clients_path=clients_path or settings.clients_path,
                    communications_path=communications_path or settings.communications_path,
                    fatigue_start_date=datetime.combine(
                        fatigue_start_date, datetime.min.time()
                    ) or settings.fatigue_start_date,
                    fatigue_end_date=datetime.combine(
                        fatigue_end_date, datetime.min.time()
                    ) or settings.fatigue_end_date,
                    own_history_min_count=own_history_min_count or settings.own_history_min_count,
                    sim_coef=sim_coef or settings.sim_coef,
                    own_coef=own_coef or settings.own_coef,
                    fatigue_coefficient_positive=fatigue_coefficient_positive or settings.fatigue_coefficient_positive,
                    fatigue_coefficient_negative=fatigue_coefficient_negative or settings.fatigue_coefficient_negative,
                    unsuccessful_comms_threshold=unsuccessful_comms_threshold or settings.unsuccessful_comms_threshold,
                    manual_mode_filter_history_by_pin=manual_mode_filter_history_by_pin or settings.manual_mode_filter_history_by_pin,
                )
                st.session_state.runtime_settings = runtime_settings
                st.session_state.demo_predictions = {}
                st.session_state.pop("manual_result", None)
                st.session_state.pop("manual_history", None)
                st.success("Настройки применены.")
        return runtime_settings

    def _score_demo_clients(
        self,
        clients: pd.DataFrame,
        comms: pd.DataFrame,
        comm_type: CommType,
        runtime_settings: Settings,
    ) -> dict[str, Prediction]:
        predictions: dict[str, Prediction] = {}
        for _, row in clients.iterrows():
            profile = self._build_client(row)
            comm_history = comms.loc[comms["client_pin"] == profile.client_pin]
            prediction = self._client_comm_service.score(
                profile=profile,
                comm_type=comm_type,
                comm_history=comm_history,
                clients_db=clients,
                comm_db=comms,
                runtime_settings=runtime_settings,
                **runtime_settings.score_kwargs,
            )
            predictions[str(profile.client_pin)] = prediction
        return predictions

    def _render_demo(self, comm_type: CommType, runtime_settings: Settings) -> None:
        st.subheader("Оценка по файлам")
        st.caption(
            f"Источник похожих: {runtime_settings.clients_path} и {runtime_settings.communications_path}"
        )
        predictions_by_type = st.session_state.setdefault("demo_predictions", {})
        calculate_requested = st.button("Оценить всех", type="primary", width="stretch")
        comm_type_key = comm_type.value

        if calculate_requested:
            predictions_by_type.pop(comm_type_key, None)

        if comm_type_key not in predictions_by_type and not calculate_requested:
            st.info("Выберите тип коммуникации и нажмите «Оценить всех».")
            return

        clients_result = self._load_demo_clients(runtime_settings.clients_path)
        if self._render_sanitization_issues(clients_result):
            return
        clients = clients_result.data
        comms_result = self._load_demo_comms(runtime_settings.communications_path)
        if self._render_sanitization_issues(comms_result):
            return
        comms = comms_result.data
        if comm_type_key not in predictions_by_type:
            predictions_by_type[comm_type_key] = self._score_demo_clients(
                clients, comms, comm_type, runtime_settings
            )
        predictions = predictions_by_type[comm_type_key]

        table = clients[["client_pin", "age_years", "city"]].copy()
        table["P"] = [
            f"{predictions[str(pin)].score:.1%}" for pin in table["client_pin"]
        ]
        table["n_sim"] = [predictions[str(pin)].n_sim for pin in table["client_pin"]]
        table["Вердикт"] = [
            predictions[str(pin)].verdict for pin in table["client_pin"]
        ]
        st.dataframe(table, width="stretch", hide_index=True)

        selected_pin = st.selectbox(
            "Клиент для детализации",
            options=clients["client_pin"].astype(str).tolist(),
            key="demo_selected_pin",
        )
        profile = clients.loc[clients["client_pin"].astype(str) == selected_pin].iloc[0]
        st.caption(
            f"Профиль: {profile['age_years']} лет · {profile['city']} · {COMM_TYPE_LABELS[comm_type]}"
        )
        self._render_calculation(predictions[selected_pin])
        selected_comms = comms.loc[comms["client_pin"].astype(str) == selected_pin]
        self._render_recent_communications(selected_comms, f"demo_{selected_pin}")

    def _sanitize_manual_history(
        self, csv_text: str, uploaded_file: st.typing.UploadedFile | None
    ) -> CsvSanitizationResult:
        source = uploaded_file if uploaded_file is not None else StringIO(csv_text)
        # Если файл не загружен и текст пустой, используем заголовки модели Communication
        if uploaded_file is None and not csv_text.strip():
            source = StringIO(",".join(field.name for field in fields(Communication)))
        return self._csv_sanitizer.read_and_sanitize(source, Communication)

    def _render_manual(self, comm_type: CommType, runtime_settings: Settings) -> None:
        st.subheader("Профиль клиента")
        with st.form("manual_score"):
            row_one = st.columns(3)
            pin = row_one[0].text_input("PIN", value="manual")
            age = row_one[1].number_input(
                "Возраст", min_value=18, max_value=100, value=30
            )
            city = row_one[2].text_input("Город", placeholder="Например, Москва")

            row_two = st.columns(4)
            salary_flag = row_two[0].selectbox(
                "Зарплатный флаг", ("", "N", "Y"), help="Пустое значение означает 'N'"
            )
            staff_flag = row_two[1].selectbox("Сотрудник", ("N", "Y"))
            bankrupt_flag = row_two[2].selectbox("Банкрот", ("N", "Y"))
            delinquency_flag = row_two[3].selectbox("Текущая просрочка", ("N", "Y"))
            products = st.text_input("Продукты", placeholder="debit;salary")
            history_csv = st.text_area(
                "История коммуникаций (CSV с заголовком)",
                height=220,
                placeholder=",".join(field.name for field in fields(Communication)),
                help="Вставьте CSV истории клиента. Справочник похожих остаётся штатным. `client_pin` не учитывается, подразумевается что данные уже фильтрованы по нужному клиенту.",
            )
            uploaded_history = st.file_uploader(
                "Или загрузите CSV истории",
                type="csv",
                help="Если выбран файл, для расчёта будет использован он, а не текстовое поле.",
            )
            submitted = st.form_submit_button(
                "Получить вердикт", type="primary", width="stretch"
            )

        if submitted:
            try:
                if isinstance(pin, str):
                    pin = int(pin)
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid client_pin, cannot properly filter similar clients: {pin}"
                )

            sanitization_result = self._sanitize_manual_history(
                history_csv, uploaded_history
            )
            if self._render_sanitization_issues(sanitization_result):
                return
            comm_history = sanitization_result.data
            if runtime_settings.manual_mode_filter_history_by_pin:
                try:
                    comm_history = comm_history[comm_history["client_pin"] == int(pin)]
                except ValueError:
                    logger.error(f"Invalid pin: {pin}")
                    st.error(
                        f"Включена фильтрация истории по пину. В системе считается что `client_pin` - это int. Но введено значение: {pin}"
                    )
                    return
            manual_profile = {
                "client_pin": pin or "manual",
                "age_years": age,
                "city": city,
                "salary_flag": salary_flag or "N",
                "staff_flag": staff_flag,
                "bankrupt_flag": bankrupt_flag,
                "delinquency_cur_flag": delinquency_flag,
                "products": products,
                "cltv_bucket": "",
            }
            profile = Client(**manual_profile)
            clients_result = self._load_demo_clients(runtime_settings.clients_path)
            if self._render_sanitization_issues(clients_result):
                return
            comms_result = self._load_demo_comms(runtime_settings.communications_path)
            if self._render_sanitization_issues(comms_result):
                return
            clients = clients_result.data
            comms = comms_result.data
            prediction = self._client_comm_service.score(
                profile=profile,
                comm_type=comm_type,
                comm_history=comm_history,
                clients_db=clients,
                comm_db=comms,
                runtime_settings=runtime_settings,
                **runtime_settings.score_kwargs,
            )
            st.session_state.manual_result = prediction
            st.session_state.manual_history = comm_history

        prediction = st.session_state.get("manual_result")
        if prediction is not None and prediction.comm_type == comm_type:
            self._render_calculation(prediction)
            self._render_recent_communications(
                st.session_state.manual_history, "manual"
            )
        elif prediction is not None:
            st.info("Для нового типа коммуникации получите вердикт повторно.")

    def render_app(self) -> None:
        st.set_page_config(
            page_title="Подходит ли коммуникация", page_icon="✦", layout="wide"
        )
        st.markdown(APP_CSS, unsafe_allow_html=True)
        st.markdown(
            """<section class="hero"><h1>Подходит ли коммуникация?</h1>
            <p>Оценка вероятности успеха по профилю клиента и истории коммуникаций.</p></section>""",
            unsafe_allow_html=True,
        )
        runtime_settings = self._render_settings()
        selected_comm_type = st.selectbox(
            "Тип коммуникации",
            options=CommType,
            format_func=lambda item: COMM_TYPE_LABELS[item],
        )
        comm_type = CommType(selected_comm_type)
        demo_tab, manual_tab = st.tabs(("Демо из CSV", "Ручной ввод"))
        with demo_tab:
            self._render_demo(comm_type, runtime_settings)
        with manual_tab:
            self._render_manual(comm_type, runtime_settings)
