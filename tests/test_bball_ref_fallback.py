import pytest
from unittest.mock import patch, MagicMock
from src.pipeline.bball_ref_fallback import fetch_bball_ref_standings, parse_bball_ref_standings

def test_parse_standings_valid_html():
    html = """
    <table id="confs_standings_E">
        <tr class="full_table">
            <th data-stat="team_name"><a href="...">Boston Celtics*</a></th>
            <td data-stat="wins">45</td>
            <td data-stat="losses">12</td>
        </tr>
    </table>
    <table id="confs_standings_W">
        <tr class="full_table">
            <th data-stat="team_name">Oklahoma City Thunder (1)</th>
            <td data-stat="wins">42</td>
            <td data-stat="losses">15</td>
        </tr>
    </table>
    """
    standings = parse_bball_ref_standings(html)
    assert "Boston Celtics" in standings
    assert standings["Boston Celtics"]["wins"] == 45
    assert standings["Boston Celtics"]["source"] == "basketball_reference_fallback"
    assert "Oklahoma City Thunder" in standings
    assert standings["Oklahoma City Thunder"]["losses"] == 15

@patch("requests.get")
def test_fetch_fallback_success(mock_get):
    mock_response = MagicMock()
    mock_response.text = '<table id="confs_standings_E"><tr class="full_table"><th data-stat="team_name">BOS</th><td data-stat="wins">10</td><td data-stat="losses">2</td></tr></table>'
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    
    data = fetch_bball_ref_standings()
    assert "BOS" in data
    assert data["BOS"]["wins"] == 10
    assert data["BOS"]["source"] == "basketball_reference_fallback"

@patch("requests.get")
def test_fetch_fallback_failure(mock_get):
    mock_get.side_effect = Exception("Network error")
    data = fetch_bball_ref_standings()
    assert data == {}
