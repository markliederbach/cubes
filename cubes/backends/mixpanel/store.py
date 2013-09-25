# -*- coding=utf -*-
from ...model import *
from ...browser import *
from ...stores import Store
from ...errors import *
from .mixpanel import *
from string import capwords
from cubes.common import get_logger

DIMENSION_COUNT_LIMIT = 100

DEFAULT_TIME_HIERARCHY = "ymdh"

time_dimension_md = {
    "name": "time",
    "levels": [
        { "name": "year", "label": "Year" }, 
        { "name": "month", "label": "Month", "info": { "aggregation_units": 3 }},
        { "name": "day", "label": "Day", "info": { "aggregation_units": 7 } },
        { "name": "hour", "label": "Hour", "info": { "aggregation_units": 6 } },
        { "name": "week", "label": "Week", "info": { "aggregation_units": 4 } },
        { "name": "date", "label": "Date", "info": { "aggregation_units": 7 } }
    ],
    "hierarchies": [
        {"name":"ymdh", "levels": ["year", "month", "day", "hour"]},
        {"name":"wdh", "levels": ["week", "date", "hour"]}
    ],
    "default_hierarchy_name": "ymdh",
    "info": { "is_date": True }
}

_time_dimension = create_dimension(time_dimension_md)

class MixpanelModelProvider(ModelProvider):
    def cube(self, name):
        """Creates a mixpanel cube with following variables:

        * `name` – cube name
        * `measures` – cube measures: `total` and `uniques`
        * `linked_dimensions` – list of linked dimension names
        * `mappings` – mapping of corrected dimension names

        Dimensions are Mixpanel's properties where ``$`` character is replaced
        by the underscore ``_`` character.
        """

        result = self.store.request(["events", "properties", "top"],
                            {"event":name, "limit":DIMENSION_COUNT_LIMIT})
        if not result:
            raise NoSuchCubeError(name)

        dim_names = result.keys()

        options = self.cube_options(name)
        allowed_dims = options.get("allowed_dimensions", [])
        denied_dims = options.get("denied_dimensions", [])

        dim_names = []
        for dim_name in result.keys():
            if not allowed_dims and not denied_dims:
                dim_names.append(dim_name)
            elif (allowed_dims and dim_name in allowed_dims) or \
                    (denied_dims and dim_name not in denied_dims):
                dim_names.append(dim_name)


        # Replace $ with underscore _
        dims = ["time"]
        mappings = {}

        for dim_name in dim_names:
            fixed_name = dim_name.replace("$", "_")
            fixed_name = fixed_name.replace(" ", "_")
            if fixed_name != dim_name:
                mappings[fixed_name] = dim_name
            dims.append(fixed_name)

        measures = attribute_list(["total", "unique"])
        for m in measures:
            m.aggregations = ['identity', 'sma']

        cube = Cube(name=name,
                    measures=measures,
                    linked_dimensions=dims,
                    datastore=self.store_name,
                    mappings=mappings,
                    category=self.store.category)

        # TODO: required_drilldowns might be a cube's attribute (fixed_dd?)
        cube.info = {
            "required_drilldowns": ["time"]
        }

        return cube

    def dimension(self, name):
        if name == "time":
            return _time_dimension

        level = Level(name, attribute_list([name]))
        dim = Dimension(name,
                         levels=[level])

        return dim

    def list_cubes(self):
        result = self.store.request(["events", "names"],
                                    {"type":"general", })
        cubes = []

        for name in result:
            label = capwords(name.replace("_", " "))
            cube = {
                    "name": name,
                    "label": label,
                    "category":  self.store.category
                    }
            cubes.append(cube)

        return cubes

class MixpanelStore(Store):
    def __init__(self, api_key, api_secret, category=None):
        self.mixpanel = Mixpanel(api_key, api_secret)
        self.category = category or "Mixpanel Events"
        self.logger = get_logger()

    def model_provider_name(self):
        return "mixpanel"

    def request(self, *args, **kwargs):
        """Performs a mixpanel HTTP request. Raises a BackendError when
        mixpanel returns `error` in the response."""

        self.logger.debug("Mixpanel request: %s" % (args,))

        response = self.mixpanel.request(*args, **kwargs)

        if "error" in response:
            raise BackendError("Mixpanel request error: %s" % response["error"])

        return response