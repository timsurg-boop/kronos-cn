from kronos_cn.cli import _canonical_symbol
from kronos_cn.config import market_suffix, normalize_code


def test_market_suffix_for_stocks_and_funds():
    assert market_suffix("600519") == ".SH"
    assert market_suffix("000001") == ".SZ"
    assert market_suffix("300750") == ".SZ"
    assert market_suffix("688981") == ".SH"
    assert market_suffix("830799") == ".BJ"
    assert market_suffix("513100") == ".SH"
    assert market_suffix("159985") == ".SZ"


def test_normalize_code():
    assert normalize_code("600519.SH") == "600519"
    assert normalize_code(" sz000001 ") == "000001"
    assert normalize_code("AAPLUSA") == "AAPLUSA"


def test_canonical_symbol():
    assert _canonical_symbol("spy") == "SPYUSA"
    assert _canonical_symbol("DIA-usa") == "DIAUSA"
    assert _canonical_symbol("MSFT") == "MSFTUSA"
    assert _canonical_symbol("600519") == "600519"
