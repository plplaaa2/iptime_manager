"""Authorization for router configuration entities."""

from functools import wraps

from homeassistant.exceptions import Unauthorized, UnknownUser


# Summary: Check the calling HA user before a router-changing entity action.
# Related files: button.py, number.py, select.py, switch.py.
def require_admin(method):
    """Allow administrators and HA internal calls without a user context."""
    @wraps(method)
    async def authorized(self, *args, **kwargs):
        context = self._context
        if context is not None and context.user_id:
            user = await self.hass.auth.async_get_user(context.user_id)
            if user is None:
                raise UnknownUser(context=context)
            if not user.is_admin:
                raise Unauthorized(context=context)
        return await method(self, *args, **kwargs)

    return authorized
