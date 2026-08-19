from .boligportal import BoligportalSite
from .boligzonen import BoligzonenSite

SITE_REGISTRY = {
    "boligzonen": BoligzonenSite,
    "boligportal": BoligportalSite,
}
