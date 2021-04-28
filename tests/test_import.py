import pytest


@pytest.mark.parametrize(
    "from_, import_",
    [
        ("actfw_jetson", "Display, NVArgusCameraCapture"),
    ],
)
def test_import_actfw_jetson(from_, import_):
    exec(f"""from {from_} import {import_}""")
