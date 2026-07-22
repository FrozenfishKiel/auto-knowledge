import pytest

from open_webui.utils.auto_knowledge.collector import resolve_source_user_ids


class FakeGroups:
    async def get_group_user_ids_by_ids(self, group_ids, db=None):
        assert group_ids == ["support", "sales"]
        return {
            "support": ["u-support", "u-shared"],
            "sales": ["u-sales", "u-shared"],
        }


@pytest.mark.asyncio
async def test_resolve_source_user_ids_combines_explicit_users_and_group_members():
    user_ids = await resolve_source_user_ids(
        user_ids=["u-explicit", "u-support"],
        group_ids=["support", "sales"],
        groups=FakeGroups(),
    )

    assert user_ids == ["u-explicit", "u-support", "u-shared", "u-sales"]


@pytest.mark.asyncio
async def test_resolve_source_user_ids_returns_empty_list_for_empty_selected_group():
    class EmptyGroups:
        async def get_group_user_ids_by_ids(self, group_ids, db=None):
            return {"empty-group": []}

    user_ids = await resolve_source_user_ids(
        user_ids=None,
        group_ids=["empty-group"],
        groups=EmptyGroups(),
    )

    assert user_ids == []
