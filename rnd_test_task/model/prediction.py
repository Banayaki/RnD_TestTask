from dataclasses import dataclass

from .enums import CommType


@dataclass
class Prediction:
    p_sim: float
    n_sim: int
    p_own: float
    n_own: int
    fatigue: float
    score: float
    age_bin: str
    salary_bin: str
    delinq_bin: str
    pin: int | str
    comm_type: CommType

    @property
    def verdict(self) -> str:
        """
        Вердикт определяется следующими правилами:
        - `n_sim < 10` → `мало данных`;
        - иначе `P >= 0.30` → `подходит`;
        - иначе `P >= 0.15` → `спорно`;
        - иначе → `не подходит`.
        """
        if self.n_sim < 10:
            return "Мало данных"
        if self.score >= 0.30:
            return "Подходит"
        if self.score >= 0.15:
            return "Спорно"
        return "Не подходит"
