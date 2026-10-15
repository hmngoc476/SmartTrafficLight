import plotly.graph_objects as go

class TrafficRenderer2D:

    # Color Codes for 2D Map Background Details
    color_bg = "#ffffff"  # Background -> While
    color_center_box = "#f6f7f8"  # The center square (where 4 direction meet) -> White gray
    color_road = "#e1e5e8"  # Road way -> Light gray
    color_lane_line = "#9da7ae"  # Road markings / Dashed line -> Gray
    color_stop_line = "#263238"  # Stop line -> Super dark green (nearly black)


    # Color Codes for Signal Light
    color_signal_red = "#aa4a4a"
    color_signal_green = "#40805b"
    color_signal_yellow = "#f1c40f"


    # Color Codes for Vehicle Details
    vehicle_colors = {
        "APPROACHING": {"fill": "#d9e3eb", "border": "#838b90", "name": "APPROACHING"},
        "STOPPED": {"fill": "#6d7982", "border": "#49555d", "name": "STOPPED"},
        "CROSSING": {"fill": "#91b5ad", "border": "#5c7473", "name": "CROSSING"}
    }
    # Light blue: "#d9e3eb"
    # Dark gray blue: "#838b90"
    # Dark gray: "#6d7982"
    # Super dark gray: "#49555d"
    # "#91b5ad"  # Light green: "#91b5ad"
    # Dark green: "#5c7473"

    def __init__(self, visible_range_m: float = 60.0, intersection_width_m: float = 16.0):
        self.visible_range_m = visible_range_m
        self.intersection_width_m = intersection_width_m
        self.half_width = intersection_width_m / 2.0
        self.r_corner = 0.6  # r: Corner rounding radius (meters)

    # Create Vehicle Shape
    @staticmethod
    def create_rounded_rect_path(x0: float, y0: float, x1: float, y1: float, r: float) -> str:
        """ Generate an SVG path string representing a rounded rectangle. """
        # Ensure xmin < xmax and ymin < ymax
        xmin, xmax = min(x0, x1), max(x0, x1)
        ymin, ymax = min(y0, y1), max(y0, y1)

        # Clamp radius to prevent it from exceeding half of the width or height
        r = min(r, (xmax - xmin) / 2.0, (ymax - ymin) / 2.0)

        # SVG commands used below: M = Move, L = Line (edges), Q = Curve (corners), Z = Close path
        # Build the path clockwise: Alternate between straight lines (L) and corner curves (Q)
        return (
            f"M {xmin + r},{ymin} "
            f"L {xmax - r},{ymin} Q {xmax},{ymin} {xmax},{ymin + r} "
            f"L {xmax},{ymax - r} Q {xmax},{ymax} {xmax - r},{ymax} "
            f"L {xmin + r},{ymax} Q {xmin},{ymax} {xmin},{ymax - r} "
            f"L {xmin},{ymin + r} Q {xmin},{ymin} {xmin + r},{ymin} Z"
        )

    def _draw_infrastructure(self, fig: go.Figure):
        """ Render the complete intersection infrastructure (roadways, lane markings, and stop lines). """
        # y-axis (North - South)
        fig.add_shape(
            type="rect",
            x0=-self.half_width, y0=-self.visible_range_m,
            x1=self.half_width, y1=self.visible_range_m,
            fillcolor=self.color_road, line=dict(width=0), layer="below"
        )
        # x-axis (East - West)
        fig.add_shape(
            type="rect",
            x0=-self.visible_range_m, y0=-self.half_width,
            x1=self.visible_range_m, y1=self.half_width,
            fillcolor=self.color_road, line=dict(width=0), layer="below"
        )
        # The center square
        fig.add_shape(
            type="rect",
            x0=-self.half_width, y0=-self.half_width,
            x1=self.half_width, y1=self.half_width,
            fillcolor=self.color_center_box,
            line=dict(color=self.color_lane_line, width=1, dash="dash"),
            layer="below"
        )
        # Road markings
        fig.add_shape(type="line", x0=0, y0=-self.visible_range_m, x1=0, y1=-self.half_width,
                      line=dict(color=self.color_lane_line, width=1.5, dash="dash"))
        fig.add_shape(type="line", x0=0, y0=self.half_width, x1=0, y1=self.visible_range_m,
                      line=dict(color=self.color_lane_line, width=1.5, dash="dash"))
        fig.add_shape(type="line", x0=-self.visible_range_m, y0=0, x1=-self.half_width, y1=0,
                      line=dict(color=self.color_lane_line, width=1.5, dash="dash"))
        fig.add_shape(type="line", x0=self.half_width, y0=0, x1=self.visible_range_m, y1=0,
                      line=dict(color=self.color_lane_line, width=1.5, dash="dash"))

        # Stop line
        fig.add_shape(type="line", x0=-self.half_width, y0=-self.half_width, x1=0, y1=-self.half_width,
                      line=dict(color=self.color_stop_line, width=3.5))
        fig.add_shape(type="line", x0=0, y0=self.half_width, x1=self.half_width, y1=self.half_width,
                      line=dict(color=self.color_stop_line, width=3.5))
        fig.add_shape(type="line", x0=-self.half_width, y0=0, x1=-self.half_width, y1=self.half_width,
                      line=dict(color=self.color_stop_line, width=3.5))
        fig.add_shape(type="line", x0=self.half_width, y0=-self.half_width, x1=self.half_width, y1=0,
                      line=dict(color=self.color_stop_line, width=3.5))

    def _draw_signals(self, fig: go.Figure, snapshot):
        """ Draw signal lights at the intersection corners """
        current_phase = getattr(snapshot, "phase", "NS_GREEN")
        ns_color = self.color_signal_green if "NS_GREEN" in current_phase else (
            self.color_signal_yellow if "NS_YELLOW" in current_phase else self.color_signal_red)
        ew_color = self.color_signal_green if "EW_GREEN" in current_phase else (
            self.color_signal_yellow if "EW_YELLOW" in current_phase else self.color_signal_red)

        sig_size = 1.5
        hw = self.half_width

        # NS Signals
        fig.add_shape(type="circle", x0=-sig_size, y0=-hw - sig_size, x1=0, y1=-hw, fillcolor=ns_color, line_width=1)
        fig.add_shape(type="circle", x0=0, y0=hw, x1=sig_size, y1=hw + sig_size, fillcolor=ns_color, line_width=1)
        # EW Signals
        fig.add_shape(type="circle", x0=hw, y0=-sig_size, x1=hw + sig_size, y1=0, fillcolor=ew_color, line_width=1)
        fig.add_shape(type="circle", x0=-hw - sig_size, y0=0, x1=-hw, y1=sig_size, fillcolor=ew_color, line_width=1)


    def _draw_vehicles_optimized(self, fig: go.Figure, snapshot):
        """
        Render vehicles: Group all vehicles with the same state into a single SVG string.
        Reduce the Plotly Draw call cost from O(N) to O(1).
        """
        if not snapshot or not hasattr(snapshot, "vehicles"):
            return

        # SVG paths and Scatter data accumulators
        svg_paths = {"APPROACHING": "", "STOPPED": "", "CROSSING": ""}
        scatter_data = {
            "APPROACHING": {"x": [], "y": [], "id": []},
            "STOPPED": {"x": [], "y": [], "id": []},
            "CROSSING": {"x": [], "y": [], "id": []}
        }

        # 1. PROCESS VEHICLES O(N): Calculate bounds and accumulate SVG paths
        for v in snapshot.vehicles:
            x, y = getattr(v, "x", 0.0), getattr(v, "y", 0.0)
            origin = getattr(v, "origin", "N")
            state = getattr(v, "motion_state", "APPROACHING")
            safe_state = state if state in svg_paths else "APPROACHING"

            # Get vehicle length from user-configured properties, width is fixed
            v_len = getattr(v, "length_m", 4.5)
            v_width = 2.0

            # Calculate bounding box based on direction
            if origin in ("N", "S"):
                x0, x1 = x - v_width / 2.0, x + v_width / 2.0
                y0, y1 = y - v_len / 2.0, y + v_len / 2.0
            else:
                x0, x1 = x - v_len / 2.0, x + v_len / 2.0
                y0, y1 = y - v_width / 2.0, y + v_width / 2.0

                # Accumulate SVG path
                svg_paths[safe_state] += self.create_rounded_rect_path(x0, y0, x1, y1, self.r_corner) + " "

                # Save data for text labels
                scatter_data[safe_state]["x"].append(x)
                scatter_data[safe_state]["y"].append(y)
                scatter_data[safe_state]["id"].append(getattr(v, "vehicle_id", "V"))

        # 2. DRAW TO PLOTLY O(1)
        for state, color_info in self.vehicle_colors.items():
            # Add grouped shapes
            if svg_paths[state]:
                fig.add_shape(
                    type="path", path=svg_paths[state],
                    fillcolor=color_info["fill"], line=dict(color=color_info["border"], width=1.5),
                    layer="above"
                )
                # Dummy trace for Legend
                fig.add_trace(go.Scatter(
                    x=[None], y=[None], mode="markers", name=color_info["name"],
                    marker=dict(size=12, symbol="square", color=color_info["fill"],
                                line=dict(width=1.5, color=color_info["border"]))
                ))

                # Add text IDs
                if scatter_data[state]["x"]:
                    fig.add_trace(go.Scatter(
                        x=scatter_data[state]["x"], y=scatter_data[state]["y"],
                        mode="text", text=scatter_data[state]["id"],
                        textfont=dict(size=9, color="#1e293b"), showlegend=False, hoverinfo="none"
                    ))

    def render(self, snapshot) -> go.Figure:
        """ Entry point to render the 2D figure. """
        fig = go.Figure()
        self._draw_infrastructure(fig)
        self._draw_signals(fig, snapshot)
        self._draw_vehicles_optimized(fig, snapshot)

        # Apply strict 1:1 scale layout
        fig.update_layout(
            template="plotly_white", paper_bgcolor=self.color_bg, plot_bgcolor=self.color_bg,
            title="Bản đồ 2D · x dương Đông, y dương Nam · đơn vị mét",
            xaxis=dict(range=[-self.visible_range_m, self.visible_range_m], showgrid=False, zeroline=False,
                       visible=False),
            yaxis=dict(range=[-self.visible_range_m, self.visible_range_m], showgrid=False, zeroline=False,
                       visible=False, scaleanchor="x", scaleratio=1),
            margin=dict(l=10, r=10, t=40, b=10),
            legend=dict(orientation="v", yanchor="top", y=0.98, xanchor="right", x=0.98)
        )
        return fig

# Wrapper function for app.py
def render_traffic_2d(snapshot, visible_range_m: float = 60.0, intersection_width_m: float = 16.0) -> go.Figure:
    return TrafficRenderer2D(visible_range_m, intersection_width_m).render(snapshot)
