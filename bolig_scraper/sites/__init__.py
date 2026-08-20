from .boligportal import BoligportalSite
from .boligzonen import BoligzonenSite
from .munkebjergpark import MunkebjergparkSite

SITE_REGISTRY = {
    "boligzonen": BoligzonenSite,
    "boligportal": BoligportalSite,
    "munkebjergpark": MunkebjergparkSite,
}
