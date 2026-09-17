from abc import ABC, abstractmethod

import pandas as pd

from model import Client, CommType, Prediction
from settings import Settings


class ClientCommService(ABC):
    @abstractmethod
    def score(
        self,
        profile: Client,
        comm_type: CommType,
        comm_history: pd.DataFrame,
        clients_db: pd.DataFrame,
        comm_db: pd.DataFrame,
        runtime_settings: Settings | None = None,
        **kwargs,
    ) -> Prediction:
        """
        Метод вычсиляющий вероятность успешной коммуникации `comm_type` для клиента `profile` по переданным данным
        истории коммуникации `comm_history`, базе клиентов `clients_db` и базе коммуникаций `comm_db`.

        Обычно `clients_db` и `comm_db` загружаются из предоставленных в задании CSV-файлов.

        !Важно: в задании просят что бы функция принимала 4 аргумента, но clients_db и comm_db будто удобнее передать разными параметрами.
        TODO: Проверить, стоит ли передавать их разными параметрами.
        """
        ...
