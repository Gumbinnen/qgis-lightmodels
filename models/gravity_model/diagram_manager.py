from .colors import BLUE_PALETTES
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import numpy as np

# TODO: USE FIELDS / PROPERTIES INSTEAD OF CONSTANS?
AX_TITLE_PARAMS = dict(fontsize=10, pad=40)
                            
PIE_WEDGE_PROPS = dict(width=0.5, edgecolor='white', linewidth=1)
PIE_PARAMS = dict(wedgeprops=PIE_WEDGE_PROPS, startangle = 0)

ANNOTATION_TEXT_FORMAT = ' '.join(['{}: {}\n', '{}: {}\n', '{:.1f}%'])
ANNOTATION_PARAMS = dict(arrowprops=dict(arrowstyle='-'),
                         bbox=dict(boxstyle='round,pad=0.3', edgecolor='None', fc="w", ec="k", lw=0.72),
                         zorder=0, va='center')

SUBPLOT_ADJUSTMENT = dict(top=0.77, bottom=0.15, left=0.0, right=1)

ON_CLICK_STYLE_PARAMS = dict(alpha=0.35, linewidth=1, zorder=1, accent_alpha=0.35, accent_linewidth=2, accent_zorder=2)

class GravityModelDiagramManager:
    def __init__(self, parent=None):        
        self._selected_field = None
        
        self.ui_widget = parent.ui_widget
        self.ui_widget.diagram_field_selected.connect(self.new_diagram_field)

    @property
    def selected_field(self):
        return self._selected_field
    
    def new_diagram_field(self, field_name):
        self._selected_field = field_name

    def update(self, diagram_canvas):
        self.ui_widget.diagram_layout.takeAt(0).widget().deleteLater()
        self.ui_widget.diagram_layout.addWidget(diagram_canvas)

    def construct_pie(self, diagram_data):
        def percentage(part, whole):
            return 100*float(part)/float(whole)
                
        # TODO: rewrite
        def update_annotations_and_wedges(wedge_index, wedges, annotations,
                                          alpha, linewidth, zorder,
                                          disregard_alpha, accent_linewidth, accent_order):
            
            wedge_style_params = dict(alpha=alpha, linewidth=linewidth)
            annotation_style_params = dict(alpha=alpha, zorder=zorder)
            bbox_alpha = alpha
            
            if wedge_index is not None:
                wedge_style_params = dict(alpha=disregard_alpha, linewidth=linewidth)
                annotation_style_params = dict(alpha=disregard_alpha, zorder=zorder)
                bbox_alpha = disregard_alpha
            
            
            # Стандартные параметры аннотаций (alpha, linewidth, zorder)
            for annotation in annotations:
                annotation.set(**annotation_style_params)
                # Updata annotation alpha
                bbox = annotation.get_bbox_patch()
                r, g, b, _ = bbox.get_facecolor()
                bbox.set_facecolor((r, g, b, bbox_alpha))
                accent_annotation.set_bbox(bbox)
            for wedge in wedges:
                wedge.set(**wedge_style_params)
            
            # Если индекс существует, изменить долю и соответсвующую аннотацию
            # Параметры акцента (accent_alpha, accent_linewidth, accent_order)
            if wedge_index is not None:
                wedge_style_params = dict(alpha=alpha, linewidth=accent_linewidth)
                annotation_style_params = dict(alpha=alpha, zorder=accent_order)
                bbox_alpha = alpha
                
                accent_annotation = annotations[wedge_index]
                accent_wedge = wedges[wedge_index]
                
                accent_wedge.set(**wedge_style_params)                
                accent_annotation.set(**annotation_style_params)
                
                bbox = accent_annotation.get_bbox_patch()
                r, g, b, _ = bbox.get_facecolor()
                bbox.set_facecolor((r, g, b, bbox_alpha))
                accent_annotation.set_bbox(bbox)
                
            # Обновить диаграмму
            plt.draw()
        
        def on_wedge_click(event, wedges, annotations, style_params):
            if event.inaxes != ax:
                return
            
            center = np.array([0, 0])  # Center of the pie chart
            xy = np.array([event.xdata, event.ydata])  # Coordinates of the click event
            angles = np.arctan2(xy[1] - center[1], xy[0] - center[0])
            angles %= 2*np.pi  # Ensure angle is within [0, 360] degrees
            angles[angles < 0] += 2*np.pi # Все отрицательные углы переводятся в эквивалентные положительные (+2пи)
            distances = np.sqrt(np.sum((xy - center)**2, axis=0))
            # Calculate значения theta1 and theta2 для каждой доли
            theta_values = np.deg2rad(np.array([[wedge.theta1, wedge.theta2] for wedge in wedges]))
            # Индекс кликнутых долей
            wedge_indixes = np.where((theta_values[:, 0] <= angles) & (angles <= theta_values[:, 1])
                                     & (distances <= np.array([wedge.r + 1 for wedge in wedges])))[0]

            wedge_index = None
            # Если клик пришёлся хотя бы на одну из долей (чаще всего wedge_indixes 0 или 1)
            if len(wedge_indixes) > 0:
                wedge_index = wedge_indixes[0]
            
            update_annotations_and_wedges(wedge_index, wedges, annotations, **style_params)

        # Diagram data is dict where each value is dict:
        # center_id — ID центральной точки
        # c_value — Значение атрибута центральной точки. Атрибут выбран в diagram_field
        # f_prob_value — Значение вероятности, полученное в результате работы гравитационной модели
        # diagram_data[c_id] = {c_value: f_prob_value}
        centers_count = len(diagram_data)
        
        if centers_count == 0:
            return
        
        # Если количество центров > 10, оставить только 10 наибольших
        if centers_count > 6:
            diagram_data_sorted_by_WHATEXACTLY = diagram_data
            diagram_data = trim_n(diagram_data, 6) # + [др.]
        
        # Extract values from diagram_data
        center_ids = list(diagram_data.keys())
        center_values = [list(value_data.keys())[0] for value_data in diagram_data.values()]
        prob_values = [(value_data.values())[0] for value_data in diagram_data.values()]
        prob_values_sum = sum(prob_values)
        
        # New var names for data_diagram values.
        u_ids = center_ids
        value_texts = center_values
        values_pct = [percentage(prob_value, prob_values_sum) for prob_value in prob_values]
        
        # Настройки диаграммы
        colors = BLUE_PALETTES['light_blue']
        subplots_adjustment = SUBPLOT_ADJUSTMENT
        ax_title_params = AX_TITLE_PARAMS
        pie_params = PIE_PARAMS
        annotation_text_format = ANNOTATION_TEXT_FORMAT
        annotation_params = ANNOTATION_PARAMS
        on_click_style_params = ON_CLICK_STYLE_PARAMS
        
        # Начало создания диаграммы.
        fig, ax = plt.subplots()
        
        fig.subplots_adjust(**subplots_adjustment)
        
        ax.set_title('Распределение потребителей среди поставщиков', **ax_title_params)
        pie = ax.pie(x, colors=colors, **pie_params)
        wedges = pie[0]        
        annotations = []

        for wedge, u_id, value_text, value_pct in zip(wedges, u_ids, value_texts, values_pct):
            # Предотвратить слишком длинный текст в аннотации
            if len(value_text) > 19:
                value_text = value_text[:18]+'…'
            
            start_angle_deg = (wedge.theta1 + wedge.theta2)/2 # Mid-angle of the slice
            start_angle_rad = np.deg2rad(start_angle_deg)
            x = np.cos(start_angle_rad)
            y = np.sin(start_angle_rad)
            text_x = 1.35*np.sign(x)
            text_y = 1.4*y
            annotation_params.update(dict(xy=(x, y), xytext=(text_x, text_y)))

            # TODO: set self._uid_field and self._selected_field
            # TODO: what is in self._uid_field and self._selected_field?
            # TODO: create get_name() or smth
            uid_name = get_name(self._uid_field)
            value_text_name = get_name(self._selected_field)
            
            # order matters!
            format_vars = uid_name, u_id, value_text_name, value_text, value_pct
            annotation_params.update(dict(text=annotation_text_format.format(**format_vars)))
            
            horizontal_alignment = {-1: "right", 1: "left"}[int(np.sign(x))]
            annotation_params.update(dict(horizontalalignment=horizontal_alignment))
            
            connection_style = f"angle,angleA=0,angleB={start_angle_deg}"
            annotation_params['arrowprops'].update(dict(connectionstyle=connection_style))
            
            annotation = ax.annotate(**annotation_params)
            annotations.append(annotation)
        
        # TODO: disconnect mechanism
        fig.canvas.mpl_connect('button_press_event', lambda event: on_wedge_click(event, wedges, annotations, on_click_style_params))
        return FigureCanvas(fig)
