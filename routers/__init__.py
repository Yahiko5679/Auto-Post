from routers.start     import router as start_router
from routers.content   import router as content_router
from routers.settings  import router as settings_router
from routers.templates import router as templates_router
from routers.buttons   import router as buttons_router
from routers.admin     import router as admin_router


def get_all_routers():
    # ORDER MATTERS:
    # - content_router must be first after start — it owns the only F.text handler
    # - buttons_router before settings so bset_ callbacks don't leak to cfg_ handler
    return [
        start_router,
        content_router,
        buttons_router,
        settings_router,
        templates_router,
        admin_router,
    ]