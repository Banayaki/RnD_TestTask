from dataclasses import dataclass
from enum import StrEnum
from posix import stat


class AgeBin(StrEnum):
    BIN_18_24 = "18-24"
    BIN_25_34 = "25-34"
    BIN_35_44 = "35-44"
    BIN_45_54 = "45-54"
    BIN_55_PLUS = "55_plus"


@dataclass
class Client:
    client_pin: int | str
    age_years: int
    city: str
    salary_flag: str
    staff_flag: str
    bankrupt_flag: str
    delinquency_cur_flag: str
    products: str
    cltv_bucket: str

    @property
    def age_bin(self) -> AgeBin:
        return Client.calc_age_bin(self.age_years)

    @property
    def salary_bin(self) -> str:
        return Client.calc_salary_bin(self.salary_flag)

    @property
    def delinq_bin(self) -> str:
        return Client.calc_delinq_bin(self.delinquency_cur_flag)

    @staticmethod
    def calc_salary_bin(salary_flag: str) -> str:
        """
        bin = Y только если в таблице строка "Y".
        """
        if salary_flag == "Y":
            return "Y"
        else:
            return "N"

    @staticmethod
    def calc_delinq_bin(delinquency_cur_flag: str) -> str:
        """
        bin = Y только если в таблице строка "Y".
        """
        if delinquency_cur_flag == "Y":
            return "Y"
        else:
            return "N"

    @staticmethod
    def calc_age_bin(age_years: int) -> AgeBin:
        if age_years < 18:
            raise ValueError(
                "Age must be at least 18 years. Incorrect data were passed."
            )

        if age_years < 25:
            return AgeBin.BIN_18_24
        elif age_years < 35:
            return AgeBin.BIN_25_34
        elif age_years < 45:
            return AgeBin.BIN_35_44
        elif age_years < 55:
            return AgeBin.BIN_45_54
        else:
            return AgeBin.BIN_55_PLUS
