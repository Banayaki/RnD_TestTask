from datetime import datetime

import pandas as pd
import pytest

from model import AgeBin, Client, CommType, Prediction
from service import ClientCommSimpleService

COMM_TYPE = CommType.PUSH_CASHBACK
COMM_COLUMNS = (
    "comm_id",
    "client_pin",
    "comm_date",
    "comm_type",
    "channel",
    "offer_id",
    "success",
)


def make_client(client_pin: int | str = 1, **overrides: object) -> Client:
    values: dict[str, object] = {
        "client_pin": client_pin,
        "age_years": 30,
        "city": "Москва",
        "salary_flag": "Y",
        "staff_flag": "N",
        "bankrupt_flag": "N",
        "delinquency_cur_flag": "N",
        "products": "debit",
        "cltv_bucket": "low",
    }
    values.update(overrides)
    return Client(**values)


def make_clients(*clients: Client) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "client_pin": client.client_pin,
                "age_years": client.age_years,
                "city": client.city,
                "salary_flag": client.salary_flag,
                "staff_flag": client.staff_flag,
                "bankrupt_flag": client.bankrupt_flag,
                "delinquency_cur_flag": client.delinquency_cur_flag,
                "products": client.products,
                "cltv_bucket": client.cltv_bucket,
            }
            for client in clients
        ]
    )


def make_comms(
    records: list[tuple[int | str, int, object, CommType]],
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "comm_id": f"comm-{index}",
                "client_pin": client_pin,
                "comm_date": comm_date,
                "comm_type": comm_type.value,
                "channel": "push",
                "offer_id": "offer",
                "success": success,
            }
            for index, (client_pin, success, comm_date, comm_type) in enumerate(
                records
            )
        ],
        columns=COMM_COLUMNS,
    ).astype({"comm_date": "datetime64[ns]"})


def score(
    profile: Client,
    comm_history: pd.DataFrame,
    clients_db: pd.DataFrame,
    comm_db: pd.DataFrame,
    comm_type: CommType = COMM_TYPE,
) -> Prediction:
    return ClientCommSimpleService().score(
        profile=profile,
        comm_type=comm_type,
        comm_history=comm_history,
        clients_db=clients_db,
        comm_db=comm_db,
    )


@pytest.mark.parametrize(
    ("age", "expected_bin"),
    [
        (18, AgeBin.BIN_18_24),
        (24, AgeBin.BIN_18_24),
        (25, AgeBin.BIN_25_34),
        (34, AgeBin.BIN_25_34),
        (35, AgeBin.BIN_35_44),
        (44, AgeBin.BIN_35_44),
        (45, AgeBin.BIN_45_54),
        (54, AgeBin.BIN_45_54),
        (55, AgeBin.BIN_55_PLUS),
    ],
)
def test_age_bucket_boundaries(age: int, expected_bin: AgeBin) -> None:
    assert Client.calc_age_bin(age) == expected_bin


@pytest.mark.parametrize(
    ("value", "expected_bin"),
    [("Y", "Y"), ("y", "N"), ("yes", "N"), ("1", "N"), ("", "N"), (None, "N")],
)
def test_salary_bucket_requires_exact_uppercase_y(
    value: str | None, expected_bin: str
) -> None:
    assert Client.calc_salary_bin(value) == expected_bin


@pytest.mark.parametrize(
    ("value", "expected_bin"),
    [("Y", "Y"), ("y", "N"), ("yes", "N"), ("1", "N"), ("", "N"), (None, "N")],
)
def test_delinquency_bucket_requires_exact_uppercase_y(
    value: str | None, expected_bin: str
) -> None:
    assert Client.calc_delinq_bin(value) == expected_bin


def test_evaluated_pin_is_excluded_from_similar_clients() -> None:
    profile = make_client(1)
    peer = make_client(2)
    clients = make_clients(profile, peer)
    comms = make_comms(
        [
            (1, 1, datetime(2025, 1, 1), COMM_TYPE),
            (2, 0, datetime(2025, 1, 1), COMM_TYPE),
        ]
    )

    prediction = score(profile, make_comms([]), clients, comms)

    assert prediction.n_sim == 1
    assert prediction.p_sim == 0.0


def test_manual_pin_does_not_exclude_clients_from_similar_sample() -> None:
    profile = make_client("manual")
    clients = make_clients(make_client(1), make_client(2))
    comms = make_comms(
        [
            (1, 1, datetime(2025, 1, 1), COMM_TYPE),
            (2, 0, datetime(2025, 1, 1), COMM_TYPE),
        ]
    )

    prediction = score(profile, make_comms([]), clients, comms)

    assert prediction.n_sim == 2
    assert prediction.p_sim == 0.5


def test_empty_similar_sample_has_zero_score_without_division_by_zero() -> None:
    profile = make_client(1)

    prediction = score(profile, make_comms([]), make_clients(profile), make_comms([]))

    assert prediction.n_sim == 0
    assert prediction.p_sim == 0.0
    assert prediction.score == 0.0


@pytest.mark.parametrize(
    ("similar_count", "expected_verdict"),
    [(9, "Мало данных"), (10, "Подходит")],
)
def test_similar_sample_verdict_boundary(
    similar_count: int, expected_verdict: str
) -> None:
    profile = make_client(1)
    peers = [make_client(pin) for pin in range(2, similar_count + 2)]
    comms = make_comms(
        [(peer.client_pin, 1, datetime(2025, 1, 1), COMM_TYPE) for peer in peers]
    )

    prediction = score(profile, make_comms([]), make_clients(profile, *peers), comms)

    assert prediction.n_sim == similar_count
    assert prediction.verdict == expected_verdict


@pytest.mark.parametrize(
    ("own_count", "expected_score"),
    [(0, 0.5), (1, 0.5), (2, 0.5), (3, 0.65)],
)
def test_own_history_mixing_boundary(own_count: int, expected_score: float) -> None:
    profile = make_client(1)
    peers = [make_client(2), make_client(3)]
    comm_db = make_comms(
        [
            (2, 1, datetime(2025, 1, 1), COMM_TYPE),
            (3, 0, datetime(2025, 1, 1), COMM_TYPE),
        ]
    )
    own_history = make_comms(
        [(1, 1, datetime(2025, 1, 1), COMM_TYPE) for _ in range(own_count)]
    )

    prediction = score(profile, own_history, make_clients(profile, *peers), comm_db)

    assert prediction.n_own == own_count
    assert prediction.score == pytest.approx(expected_score)


def test_invalid_date_contributes_to_own_history_but_not_fatigue() -> None:
    profile = make_client(1)
    peer = make_client(2)
    own_history = make_comms([(1, 0, pd.NaT, COMM_TYPE)])
    comm_db = make_comms([(2, 1, datetime(2025, 1, 1), COMM_TYPE)])

    prediction = score(profile, own_history, make_clients(profile, peer), comm_db)

    assert prediction.n_own == 1
    assert prediction.fatigue == 1.0


@pytest.mark.parametrize("failure_date", [datetime(2026, 8, 31), datetime(2026, 9, 14)])
def test_failure_on_fatigue_window_boundary_reduces_score(
    failure_date: datetime,
) -> None:
    profile = make_client(1)
    peer = make_client(2)
    own_history = make_comms([(1, 0, failure_date, COMM_TYPE)])
    comm_db = make_comms([(2, 1, datetime(2025, 1, 1), COMM_TYPE)])

    prediction = score(profile, own_history, make_clients(profile, peer), comm_db)

    assert prediction.fatigue == 0.7


@pytest.mark.parametrize("failure_date", [datetime(2026, 8, 30), datetime(2026, 9, 15)])
def test_failure_outside_fatigue_window_does_not_reduce_score(
    failure_date: datetime,
) -> None:
    profile = make_client(1)
    peer = make_client(2)
    own_history = make_comms([(1, 0, failure_date, COMM_TYPE)])
    comm_db = make_comms([(2, 1, datetime(2025, 1, 1), COMM_TYPE)])

    prediction = score(profile, own_history, make_clients(profile, peer), comm_db)

    assert prediction.fatigue == 1.0


def test_several_fresh_successes_keep_positive_fatigue() -> None:
    profile = make_client(1)
    peer = make_client(2)
    own_history = make_comms(
        [
            (1, 1, datetime(2026, 8, 31), COMM_TYPE),
            (1, 1, datetime(2026, 9, 7), COMM_TYPE),
            (1, 1, datetime(2026, 9, 14), COMM_TYPE),
        ]
    )
    comm_db = make_comms([(2, 1, datetime(2025, 1, 1), COMM_TYPE)])

    prediction = score(profile, own_history, make_clients(profile, peer), comm_db)

    assert prediction.fatigue == 1.0


def test_single_fresh_failure_reduces_fatigue() -> None:
    profile = make_client(1)
    peer = make_client(2)
    own_history = make_comms(
        [
            (1, 1, datetime(2026, 9, 1), COMM_TYPE),
            (1, 0, datetime(2026, 9, 2), COMM_TYPE),
        ]
    )
    comm_db = make_comms([(2, 1, datetime(2025, 1, 1), COMM_TYPE)])

    prediction = score(profile, own_history, make_clients(profile, peer), comm_db)

    assert prediction.fatigue == 0.7


@pytest.mark.parametrize(
    ("score_value", "expected_verdict"),
    [(0.15, "Спорно"), (0.30, "Подходит")],
)
def test_verdict_includes_exact_score_boundaries(
    score_value: float, expected_verdict: str
) -> None:
    prediction = Prediction(
        p_sim=0.0,
        n_sim=10,
        p_own=0.0,
        n_own=0,
        fatigue=1.0,
        score=score_value,
        age_bin="25-34",
        salary_bin="Y",
        delinq_bin="N",
        pin=1,
        comm_type=COMM_TYPE,
    )

    assert prediction.verdict == expected_verdict


@pytest.mark.parametrize(
    ("score_value", "expected_verdict", "displayed_score"),
    [
        (0.14999, "Не подходит", "15.0%"),
        (0.15001, "Спорно", "15.0%"),
        (0.29999, "Спорно", "30.0%"),
        (0.30001, "Подходит", "30.0%"),
    ],
)
def test_verdict_uses_raw_score_before_display_rounding(
    score_value: float, expected_verdict: str, displayed_score: str
) -> None:
    prediction = Prediction(
        p_sim=0.0,
        n_sim=10,
        p_own=0.0,
        n_own=0,
        fatigue=1.0,
        score=score_value,
        age_bin="25-34",
        salary_bin="Y",
        delinq_bin="N",
        pin=1,
        comm_type=COMM_TYPE,
    )

    assert f"{prediction.score:.1%}" == displayed_score
    assert prediction.verdict == expected_verdict


@pytest.mark.parametrize("comm_type", list(CommType))
def test_every_communication_type_is_scored(comm_type: CommType) -> None:
    profile = make_client(1)
    peer = make_client(2)
    comm_db = make_comms([(2, 1, datetime(2025, 1, 1), comm_type)])
    own_history = make_comms([(1, 1, datetime(2025, 1, 1), comm_type)])

    prediction = score(
        profile,
        own_history,
        make_clients(profile, peer),
        comm_db,
        comm_type,
    )

    assert prediction.comm_type == comm_type
    assert prediction.n_sim == 1
