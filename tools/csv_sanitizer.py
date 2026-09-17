import traceback
from dataclasses import dataclass, fields
from os import PathLike
from typing import IO

import pandas as pd
from loguru import logger

from model.client import Client
from model.communication import Communication

VALID_SUCCESS_VALUES = frozenset({0, 1, "0", "1"})
CsvModel = type[Client] | type[Communication]


class CsvValidationError(ValueError):
    """CSV не соответствует требованиям."""


class CsvSanitizationWarning(UserWarning):
    """CSV обработан с потерей значения, допустимой по техническому заданию."""


@dataclass(frozen=True)
class CsvSanitizationResult:
    data: pd.DataFrame
    errors: list[Exception]
    warnings: list[Exception]


class CsvSanitizer:
    """Проверяет CSV профилей клиентов и истории коммуникаций."""

    def read_and_sanitize(
        self,
        source: str | PathLike[str] | IO[str] | IO[bytes],
        model: CsvModel = Communication,
    ) -> CsvSanitizationResult:
        try:
            data = pd.read_csv(source)
        except pd.errors.EmptyDataError as error:
            return self._result_with_error(
                "CSV пустой или не содержит заголовка.", error
            )
        except pd.errors.ParserError as error:
            return self._result_with_error(f"Не удалось разобрать CSV. {source}", error)
        except UnicodeDecodeError as error:
            return self._result_with_error(f"Не удалось декодировать CSV. {source}", error)
        except OSError as error:
            return self._result_with_error(f"Не удалось прочитать CSV. {source}", error)
        return self.sanitize(data, model)

    def sanitize(
        self, data: pd.DataFrame, model: CsvModel = Communication
    ) -> CsvSanitizationResult:
        """
        Производит валидацию CSV файла: проверяет соответствие структуре переданной модели.
        Также производит очистку данных: преобразует даты в datetime, пропуски/ошибки заменяет на NaT.
        """
        errors: list[Exception] = []
        warnings: list[Exception] = []
        model_error = self._validate_model(model)
        if model_error:
            return CsvSanitizationResult(data.copy(), [model_error], warnings)

        columns_error = self._validate_columns(data, model)
        if columns_error:
            return CsvSanitizationResult(data.copy(), [columns_error], warnings)

        sanitized = data.copy()
        if model is Client:
            try:
                sanitized["age_years"] = pd.to_numeric(sanitized["age_years"], errors="raise")
            except ValueError as e:
                errors.append(
                    self._issue(CsvValidationError, "Некорректные значения age_years: "
                                f"{e}.", e)
                )
            return CsvSanitizationResult(sanitized, errors, warnings)

        original_dates = sanitized["comm_date"]
        # IMPORTANT: преобразуем даты в datetime, пропуски/ошибки заменяем на NaT
        sanitized["comm_date"] = pd.to_datetime(original_dates, errors="coerce")
        invalid_date_count = int(
            (original_dates.notna() & sanitized["comm_date"].isna()).sum()
        )
        if invalid_date_count:
            warnings.append(
                self._issue(
                    CsvSanitizationWarning,
                    "Некорректные значения comm_date заменены на NaT: "
                    f"{invalid_date_count}.",
                )
            )

        invalid_success_values = self._find_invalid_success_values(sanitized["success"])
        if invalid_success_values:
            values = ", ".join(map(str, invalid_success_values))
            errors.append(
                self._issue(
                    CsvValidationError,
                    f"Недопустимые значения success: {values}.",
                )
            )
        return CsvSanitizationResult(sanitized, errors, warnings)

    @staticmethod
    def _validate_model(model: CsvModel) -> Exception | None:
        if model not in (Client, Communication):
            return CsvSanitizer._issue(
                CsvValidationError,
                "Поддерживаются только модели Client и Communication.",
            )
        return None

    @staticmethod
    def _validate_columns(
        data: pd.DataFrame, model: CsvModel
    ) -> Exception | None:
        required_columns = {field.name for field in fields(model)}
        missing_columns = required_columns.difference(data.columns)
        if missing_columns:
            columns = ", ".join(sorted(missing_columns))
            return CsvSanitizer._issue(
                CsvValidationError,
                f"В CSV отсутствуют обязательные колонки: {columns}.",
            )
        return None

    @staticmethod
    def _issue(
        issue_type: type[Exception], message: str, cause: Exception | None = None
    ) -> Exception:
        try:
            if cause is not None:
                raise issue_type(message) from cause
            raise issue_type(message)
        except issue_type as issue:
            return issue

    @staticmethod
    def _result_with_error(
        message: str, cause: Exception
    ) -> CsvSanitizationResult:
        issue = CsvSanitizer._issue(CsvValidationError, message, cause)
        logger.error("{}\n{}", message, "".join(traceback.format_exception(issue)))
        return CsvSanitizationResult(pd.DataFrame(), [issue], [])

    @staticmethod
    def _find_invalid_success_values(success: pd.Series) -> tuple[object, ...]:
        invalid = success[~success.isin(VALID_SUCCESS_VALUES)]
        return tuple(pd.unique(invalid).tolist())
