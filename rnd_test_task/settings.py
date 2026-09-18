from datetime import datetime

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    clients_path: str = "materials/clients.csv"
    communications_path: str = "materials/communications.csv"

    fatigue_start_date: datetime = datetime(2026, 8, 31)
    fatigue_end_date: datetime = datetime(2026, 9, 14)

    own_history_min_count: int = 3
    sim_coef: float = 0.7
    own_coef: float = 0.3
    fatigue_coefficient_positive: float = 1.0
    fatigue_coefficient_negative: float = 0.7
    unsuccessful_comms_threshold: int = 1

    """
    Нужно ли фильтровать историю коммуникаций по пину клиента созданного в "ручном" режиме.
    Если False, то фильтрация не производится и считается что переданные данные относятся к этому клиенту.
    """
    manual_mode_filter_history_by_pin: bool = False

    @property
    def score_kwargs(self) -> dict[str, int | float]:
        return {
            "own_history_min_count": self.own_history_min_count,
            "sim_coef": self.sim_coef,
            "own_coef": self.own_coef,
            "fatigue_coefficient_positive": self.fatigue_coefficient_positive,
            "fatigue_coefficient_negative": self.fatigue_coefficient_negative,
        }

    @field_validator("fatigue_start_date", mode="before")
    def parse_fatigue_start_date(cls, value: str | datetime) -> datetime:
        """
        Дата начала отсчета усталости.
        TODO: не учтена timzeone.
        """
        if isinstance(value, datetime):
            return value
        try:
            return datetime.strptime(value, "%d-%m-%Y")
        except ValueError:
            raise ValueError(f"Invalid date format: {value}. Should be DD-MM-YYYY")

    @field_validator("fatigue_end_date", mode="before")
    def parse_fatigue_end_date(cls, value: str | datetime) -> datetime:
        """
        Дата окончания отсчета усталости.
        TODO: не учтена timzeone.
        """
        if isinstance(value, datetime):
            return value
        try:
            return datetime.strptime(value, "%d-%m-%Y")
        except ValueError:
            raise ValueError(f"Invalid date format: {value}. Should be DD-MM-YYYY")


settings = Settings()  # pyright: ignore[reportCallIssue]
