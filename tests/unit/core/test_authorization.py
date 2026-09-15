import pytest

from ros_xolo.core.services.authorization import ActorContext, AuthorizationDenied, authorize_planner


@pytest.mark.django_db
def test_planning_permission_is_explicit_and_branch_scoped(user, organization, branch):
    with pytest.raises(AuthorizationDenied):
        authorize_planner(ActorContext(user.id, organization.id), branch.id)
