"""Contains the ring road scenario class."""

from flow.scenarios.base_scenario import Scenario
from flow.core.params import InitialConfig
from flow.core.traffic_lights import TrafficLights
from numpy import pi, sin, cos, linspace, ceil, sqrt

ADDITIONAL_NET_PARAMS = {
    # length of the ring road
    "length": 230,
    # number of lanes
    "lanes": 1,
    # speed limit for all edges
    "speed_limit": 30,
    # resolution of the curves on the ring
    "resolution": 40,
    # number of rings in the system
    "num_rings": 7
}

VEHICLE_LENGTH = 5  # length of vehicles in the network, in meters


class MultiLoopScenario(Scenario):
    """Ring road scenario."""

    def __init__(self,
                 name,
                 vehicles,
                 net_params,
                 initial_config=InitialConfig(),
                 traffic_lights=TrafficLights()):
        """Initialize a loop scenario.

        Requires from net_params:
        - length: length of the circle
        - lanes: number of lanes in the circle
        - speed_limit: max speed limit of the circle
        - resolution: number of nodes resolution

        See flow/scenarios/base_scenario.py for description of params.
        """
        for p in ADDITIONAL_NET_PARAMS.keys():
            if p not in net_params.additional_params:
                raise KeyError('Network parameter "{}" not supplied'.format(p))

        self.length = net_params.additional_params["length"]
        self.lanes = net_params.additional_params["lanes"]
        self.num_rings = net_params.additional_params["num_rings"]

        super().__init__(name, vehicles, net_params, initial_config,
                         traffic_lights)

    def specify_edge_starts(self):
        """See parent class."""
        edgelen = self.length / 4
        shift = 4 * edgelen

        edgestarts = []
        for i in range(self.num_rings):
            edgestarts += [("bottom_{}".format(i), 0 + i * shift),
                           ("right_{}".format(i), edgelen + i * shift),
                           ("top_{}".format(i), 2 * edgelen + i * shift),
                           ("left_{}".format(i), 3 * edgelen + i * shift)]

        return edgestarts

    @staticmethod
    def gen_custom_start_pos(cls, initial_config, num_vehicles, **kwargs):
        """Generate uniformly spaced starting positions on each ring.

        It is assumed that there are an equal number of vehicles per ring.
        If the perturbation term in initial_config is set to some positive
        value, then the start positions are perturbed from a uniformly spaced
        distribution by a gaussian whose std is equal to this perturbation
        term.

        Parameters
        ----------
        cls : flow.core.kernel.scenario.KernelScenario
            flow scenario kernel, with all the relevant methods implemented
        initial_config : InitialConfig type
            see flow/core/params.py
        num_vehicles : int
            number of vehicles to be placed on the network
        kwargs : dict
            extra components, usually defined during reset to overwrite initial
            config parameters

        Returns
        -------
        list of tuple (float, float)
            list of start positions [(edge0, pos0), (edge1, pos1), ...]
        list of int
            list of start lanes
        list of float
            list of start speeds
        """
        (x0, min_gap, bunching, lanes_distr, available_length,
         available_edges, initial_config) = \
            cls._get_start_pos_util(initial_config, num_vehicles, **kwargs)

        increment = available_length / num_vehicles
        vehs_per_ring = num_vehicles / cls.network.num_rings

        x = x0
        car_count = 0
        startpositions, startlanes = [], []

        # generate uniform starting positions
        while car_count < num_vehicles:
            # collect the position and lane number of each new vehicle
            pos = cls.get_edge(x)

            # place vehicles side-by-side in all available lanes on this edge
            for lane in range(min(cls.num_lanes(pos[0]), lanes_distr)):
                car_count += 1
                startpositions.append(pos)
                edge, pos = startpositions[-1]
                startpositions[-1] = edge, pos % cls.length()
                startlanes.append(lane)

                if car_count == num_vehicles:
                    break

            # 1e-13 prevents an extra car from being added in wrong place
            x = (x + increment + VEHICLE_LENGTH + min_gap) + 1e-13
            if (car_count % vehs_per_ring) == 0:
                # if we have put in the right number of cars,
                # move onto the next ring
                ring_num = int(car_count / vehs_per_ring)
                x = cls.length() * ring_num + 1e-13

        # add a perturbation to each vehicle, while not letting the vehicle
        # leave its current edge
        # if initial_config.perturbation > 0:
        #     for i in range(num_vehicles):
        #         perturb = np.random.normal(0, initial_config.perturbation)
        #         edge, pos = startpositions[i]
        #         pos = max(0, min(self.edge_length(edge), pos + perturb))
        #         startpositions[i] = (edge, pos)

        # all vehicles start with an initial speed of 0 m/s
        startvel = [0 for _ in range(len(startlanes))]

        return startpositions, startlanes, startvel

    def specify_nodes(self, net_params):
        """See parent class."""
        length = net_params.additional_params["length"]
        ring_num = net_params.additional_params["num_rings"]

        r = length / (2 * pi)
        ring_spacing = 4 * r
        num_rows = num_cols = int(ceil(sqrt(ring_num)))

        nodes = []
        i = 0
        for j in range(num_rows):
            for k in range(num_cols):
                nodes += [{
                    "id": "bottom_{}".format(i),
                    "x": 0 + j * ring_spacing,
                    "y": -r + k * ring_spacing
                }, {
                    "id": "right_{}".format(i),
                    "x": r + j * ring_spacing,
                    "y": 0 + k * ring_spacing
                }, {
                    "id": "top_{}".format(i),
                    "x": 0 + j * ring_spacing,
                    "y": r + k * ring_spacing
                }, {
                    "id": "left_{}".format(i),
                    "x": -r + j * ring_spacing,
                    "y": 0 + k * ring_spacing
                }]
                i += 1
                # FIXME this break if we don't have an exact square
                if i >= ring_num:
                    break
            if i >= ring_num:
                break

        return nodes

    def specify_edges(self, net_params):
        """See parent class."""
        length = net_params.additional_params["length"]
        resolution = net_params.additional_params["resolution"]
        ring_num = net_params.additional_params["num_rings"]
        num_rows = num_cols = int(ceil(sqrt(ring_num)))
        r = length / (2 * pi)
        ring_spacing = 4 * r
        edgelen = length / 4.
        edges = []

        i = 0

        for j in range(num_rows):
            for k in range(num_cols):
                edges += [{
                    "id":
                        "bottom_{}".format(i),
                    "type":
                        "edgeType",
                    "from":
                        "bottom_{}".format(i),
                    "to":
                        "right_{}".format(i),
                    "length":
                        edgelen,
                    "shape":
                        [
                            (r * cos(t) + j * ring_spacing,
                             r * sin(t) + k * ring_spacing)
                            for t in linspace(-pi / 2, 0, resolution)
                        ]
                }, {
                    "id":
                        "right_{}".format(i),
                    "type":
                        "edgeType",
                    "from":
                        "right_{}".format(i),
                    "to":
                        "top_{}".format(i),
                    "length":
                        edgelen,
                    "shape":
                        [
                            (r * cos(t) + j * ring_spacing,
                             r * sin(t) + k * ring_spacing)
                            for t in linspace(0, pi / 2, resolution)
                        ]
                }, {
                    "id":
                        "top_{}".format(i),
                    "type":
                        "edgeType",
                    "from":
                        "top_{}".format(i),
                    "to":
                        "left_{}".format(i),
                    "length":
                        edgelen,
                    "shape":
                        [
                            (r * cos(t) + j * ring_spacing,
                             r * sin(t) + k * ring_spacing)
                            for t in linspace(pi / 2, pi, resolution)
                        ]
                }, {
                    "id":
                        "left_{}".format(i),
                    "type":
                        "edgeType",
                    "from":
                        "left_{}".format(i),
                    "to":
                        "bottom_{}".format(i),
                    "length":
                        edgelen,
                    "shape":
                        [
                            (r * cos(t) + j * ring_spacing,
                             r * sin(t) + k * ring_spacing)
                            for t in linspace(pi, 3 * pi / 2, resolution)
                        ]
                }]
                i += 1
                if i >= ring_num:
                    break
            if i >= ring_num:
                break

        return edges

    def specify_types(self, net_params):
        """See parent class."""
        lanes = net_params.additional_params["lanes"]
        speed_limit = net_params.additional_params["speed_limit"]

        types = [{
            "id": "edgeType",
            "numLanes": lanes,
            "speed": speed_limit
        }]

        return types

    def specify_routes(self, net_params):
        """See parent class."""
        ring_num = net_params.additional_params["num_rings"]
        rts = {}
        for i in range(ring_num):
            rts.update({
                "top_{}".format(i):
                    ["top_{}".format(i),
                     "left_{}".format(i),
                     "bottom_{}".format(i),
                     "right_{}".format(i)],
                "left_{}".format(i): ["left_{}".format(i),
                                      "bottom_{}".format(i),
                                      "right_{}".format(i),
                                      "top_{}".format(i)],
                "bottom_{}".format(i): ["bottom_{}".format(i),
                                        "right_{}".format(i),
                                        "top_{}".format(i),
                                        "left_{}".format(i)],
                "right_{}".format(i): ["right_{}".format(i),
                                       "top_{}".format(i),
                                       "left_{}".format(i),
                                       "bottom_{}".format(i)]
            })

        return rts
