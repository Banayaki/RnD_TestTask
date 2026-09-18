from dataclasses import asdict
from datetime import datetime
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest
from loguru import logger
from streamlit.testing.v1 import AppTest

from rnd_test_task.model import Client, CommType
from rnd_test_task.model.communication import Communication
from rnd_test_task.service import ClientCommSimpleService
from rnd_test_task.settings import Settings
from rnd_test_task.tools import CsvSanitizer
from rnd_test_task.ui.app import StreamlitApp


def generate_comms_csv_text_with_success(success_value) -> str:
    header = "comm_id,client_pin,comm_date,comm_type,channel,offer_id,success\n"
    return header + f"h-00001,30001,2025-01-16,sms_cashback,sms,CASHBACK_5,{success_value}"


def test_broken_csv_is_rendered_as_error_without_crashing_application() -> None:
    app_file = Path(__file__).parents[1] / "rnd_test_task" / "main.py"
    app = AppTest.from_file(app_file, default_timeout=10).run()

    assert not app.exception

    app.text_area[0].set_value('comm_id,"broken').run()
    next(button for button in app.button if button.label == "Получить вердикт").click().run()

    assert not app.exception
    assert app.error
    assert app.text_area[0].value == 'comm_id,"broken'


def test_demo_and_manual_inputs_produce_identical_score() -> None:
    profile = Client(
        client_pin=1,
        age_years=30,
        city="Москва",
        salary_flag="Y",
        staff_flag="N",
        bankrupt_flag="N",
        delinquency_cur_flag="N",
        products="debit",
        cltv_bucket="low",
    )
    clients = pd.DataFrame(
        [
            {
                "client_pin": 1,
                "age_years": 30,
                "city": "Москва",
                "salary_flag": "Y",
                "staff_flag": "N",
                "bankrupt_flag": "N",
                "delinquency_cur_flag": "N",
                "products": "debit",
                "cltv_bucket": "low",
            },
            {
                "client_pin": 2,
                "age_years": 30,
                "city": "Москва",
                "salary_flag": "Y",
                "staff_flag": "N",
                "bankrupt_flag": "N",
                "delinquency_cur_flag": "N",
                "products": "debit",
                "cltv_bucket": "low",
            },
        ]
    )
    comms = pd.DataFrame(
        [
            {
                "comm_id": "own",
                "client_pin": 1,
                "comm_date": datetime(2025, 1, 1),
                "comm_type": CommType.PUSH_CASHBACK.value,
                "channel": "push",
                "offer_id": "offer",
                "success": 1,
            },
            {
                "comm_id": "similar",
                "client_pin": 2,
                "comm_date": datetime(2025, 1, 1),
                "comm_type": CommType.PUSH_CASHBACK.value,
                "channel": "push",
                "offer_id": "offer",
                "success": 0,
            },
        ]
    )
    service = ClientCommSimpleService()
    runtime_settings = Settings()
    streamlit_app = StreamlitApp(service, CsvSanitizer())

    demo_prediction = streamlit_app._score_demo_clients(
        clients.copy(), comms, CommType.PUSH_CASHBACK, runtime_settings
    )["1"]
    manual_prediction = service.score(
        profile=profile,
        comm_type=CommType.PUSH_CASHBACK,
        comm_history=comms.loc[comms["client_pin"] == 1],
        clients_db=clients.copy(),
        comm_db=comms,
        runtime_settings=runtime_settings,
        **runtime_settings.score_kwargs,
    )

    assert asdict(demo_prediction) == asdict(manual_prediction)


def test_broken_csv_returns_errors_instead_of_raising() -> None:
    result = CsvSanitizer().read_and_sanitize(StringIO('comm_id,"broken'))

    assert result.errors
    assert not result.warnings

@pytest.mark.parametrize(
    ("success_value", "expected_errors"),
    [
        (1, False),
        (0, False),
        ("1", False),
        ("0", False),
        (1.0, True),
        (0.0, True),
        ("1.0", True),
        ("0.0", True),
        ("", True),
        (None, True),
        (True, True),
        (False, True),
        ("true", True),
        ("false", True),
    ],
)
def test_broken_csv_incorrest_success_values(success_value, expected_errors: bool) -> None:
    result = CsvSanitizer().read_and_sanitize(
        StringIO(generate_comms_csv_text_with_success(success_value)),
        model=Communication
    )
    logger.debug(result.data)

    if expected_errors:
        assert result.errors
    else:
        assert not result.errors
    assert not result.warnings
