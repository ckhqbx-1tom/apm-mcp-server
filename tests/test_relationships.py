import pytest

from apm_mcp.errors import APMError
from apm_mcp.tools.relationships import get_monitor_group_topology, get_monitor_relationships
from conftest import FakeClient, load_json, load_xml


@pytest.mark.asyncio
async def test_official_dependency_shape():
    client = FakeClient({"/AppManager/xml/listDependencies": load_xml("list_dependencies.xml")})
    result = await get_monitor_relationships(client, "10000035", "1651")
    assert client.calls[-1][1] == {"resourceid": "10000035", "attributeid": "1651"}
    assert len(result["relationships"]) == 2
    assert result["relationships"][0] == {"direction": "dependency", "resource_id": "10000043",
        "display_name": "Apache Service", "monitor_type": "Apache", "attribute_id": "2100"}


@pytest.mark.asyncio
async def test_dependency_derives_official_health_attribute_id():
    client = FakeClient({"/AppManager/json/ListMonitor": load_json("list_monitor.json"),
                         "/AppManager/xml/listDependencies": load_xml("list_dependencies.xml")})
    await get_monitor_relationships(client, "10000035")
    assert client.calls[-1][1]["attributeid"] == "1651"


@pytest.mark.asyncio
async def test_official_monitor_group_topology_shape_and_bounds():
    client = FakeClient({"/AppManager/json/ListMGDetails": load_json("list_mg_details.json")})
    result = await get_monitor_group_topology(client, monitor_group_id="20000036", limit=10)
    assert client.calls[-1][1] == {"groupId": "20000036"}
    assert result["group"] == {"resource_id": "20000036", "display_name": "Applications Manager"}
    assert result["members"][0]["resource_id"] == "20000043"
    assert result["child_groups"][0]["resource_id"] == "20000103"


@pytest.mark.asyncio
async def test_monitor_group_requires_unambiguous_identifier():
    with pytest.raises(APMError):
        await get_monitor_group_topology(FakeClient({}))
    with pytest.raises(APMError):
        await get_monitor_group_topology(FakeClient({}), "1", "name")
