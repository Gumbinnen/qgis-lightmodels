from .colors import BLUE_PALETTES
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import numpy as np

# TODO: USE FIELDS / PROPERTIES INSTEAD OF CONSTANS?
DIAGRAM_TITLE = 'Распределение потребителей среди поставщиков'
DIAGRAM_TITLE_PARAMS = dict(fontsize=10, pad=40)

PIE_PARAMS = dict(
    colors=BLUE_PALETTES['light_blue'], startangle = 0,
    wedgeprops=dict(width=0.5, edgecolor='white', linewidth=1)
)

ANNOTATION_PARAMS = dict(
    zorder=0, va='center',
    arrowprops=dict(arrowstyle='-'),
    bbox=dict(boxstyle='round,pad=0.3', edgecolor='None', fc="w", ec="k", lw=0.72)
)

SUBPLOT_ADJUSTMENT = dict(top=0.77, bottom=0.15, left=0.0, right=1)

ON_CLICK_STYLE_PARAMS = dict(alpha=0.35, linewidth=1, zorder=1, dull_alpha=0.35, accent_linewidth=2, accent_zorder=2)


class GravityModelDiagramManager:
    def __init__(self, parent=None):
        self._selected_field = None
        self._diagram_highlighted = False
        
        self.ui_widget = parent.ui_widget
        self.ui_widget.diagram_field_selected.connect(self.new_diagram_field)

    @property
    def selected_field(self):
        return self._selected_field
    
    @property
    def diagram_highlight_state(self):
        return self._diagram_highlighted
    
    def new_diagram_field(self, field_name):
        self._selected_field = field_name

    def update(self, diagram_canvas):
        if self.ui_widget.diagram_layout.count() > 0:
            old_chart = self.ui_widget.diagram_layout.takeAt(0).widget()
            if old_chart:
                old_chart.deleteLater()
        self.ui_widget.diagram_layout.addWidget(diagram_canvas)

    def construct_pie(self, diagram_data):
        def percentage(part, whole):
            return 100 * float(part) / float(whole)

        def apply_styles_to_all(wedge_style_params, annotation_style_params, bbox_alpha):
            for annotation in annotations:
                annotation.set(**annotation_style_params)
                # Updata annotation alpha
                bbox = annotation.get_bbox_patch()
                r, g, b, _ = bbox.get_facecolor()
                bbox.set_facecolor((r, g, b, bbox_alpha))
                annotation.set_bbox(bbox)
            for wedge in wedges:
                wedge.set(**wedge_style_params)
                
        def apply_styles_to_selected(selected_wedge_index, wedge_style_params, annotation_style_params, bbox_alpha):
            accent_annotation = annotations[selected_wedge_index]
            accent_wedge = wedges[selected_wedge_index]
            
            accent_wedge.set(**wedge_style_params)                
            accent_annotation.set(**annotation_style_params)
            
            bbox = accent_annotation.get_bbox_patch()
            r, g, b, _ = bbox.get_facecolor()
            bbox.set_facecolor((r, g, b, bbox_alpha))
            accent_annotation.set_bbox(bbox)
        # TODO: Вероятно, apply_styles_to_…() нуждаются в wedges и annotations.
        # Или wedges и annotations не нужны никому, начиная с on_wedge_click()? 🤨
        def update_style(
                selected_wedge_index,   # index of selected wedge
                is_highlighted,         # is pie wedge highlighted
                wedges, annotations,    # list of wedges and annotations
                alpha, linewidth, zorder, dull_alpha, accent_linewidth, accent_order # style params
            ) -> bool:
            
            if not selected_wedge_index:
                if not is_highlighted:
                    return False
                
                # All to default style.                
                apply_styles_to_all(
                    wedge_style_params = dict(alpha=alpha, linewidth=linewidth),
                    annotation_style_params = dict(alpha=alpha, zorder=zorder),
                    bbox_alpha = alpha
                )
                return False
            
            # All to default style.
            apply_styles_to_all(
                wedge_style_params = dict(alpha=dull_alpha, linewidth=linewidth),
                annotation_style_params = dict(alpha=dull_alpha, zorder=zorder),
                bbox_alpha = alpha
            )
            # Selected wedge to highlight style.
            apply_styles_to_selected(
                selected_wedge_index=selected_wedge_index,
                wedge_style_params = dict(alpha=alpha, linewidth=accent_linewidth),
                annotation_style_params = dict(alpha=alpha, zorder=accent_order),
                bbox_alpha = alpha
            )            
            return True

        def on_wedge_click(event, wedges, annotations, style_params):
            if event.inaxes != ax:
                return
            
            center = np.array([0, 0])  # Center of the pie chart.
            xy = np.array([event.xdata, event.ydata])  # Coordinates of the click event.
            angles = np.arctan2(xy[1] - center[1], xy[0] - center[0])
            angles %= 2*np.pi  # Ensure angle is within [0, 360] degrees.
            angles[angles < 0] += 2*np.pi # Все отрицательные углы переводятся в эквивалентные положительные (+2пи).
            distances = np.sqrt(np.sum((xy - center)**2, axis=0))
            # Вычисляем значения theta1 and theta2 для каждой доли.
            theta_values = np.deg2rad(np.array([[wedge.theta1, wedge.theta2] for wedge in wedges]))
            # Индекс кликнутых долей
            wedge_indixes = np.where((theta_values[:, 0] <= angles) & (angles <= theta_values[:, 1])
                                     & (distances <= np.array([wedge.r + 1 for wedge in wedges])))[0]

            wedge_index = None
            # Если клик пришёлся хотя бы на одну из долей (чаще всего wedge_indixes 0 или 1).
            if len(wedge_indixes) > 0:
                wedge_index = wedge_indixes[0]
            
            self.diagram_highlight_state = update_style(
                wedge_index,
                self.diagram_highlight_state,
                wedges, annotations,
                **style_params
            )
            
            # Обновить диаграмму.
            plt.draw()

        def trim_n(sorted_diagram_data, n_count):
            # Если кол-во элементов и так меньше или равно n_count, вернуть список без изменений.
            if sorted_diagram_data.count() <= n_count:
                return trimmed_data

            # Первые n_count элементов.
            top_n = sorted_diagram_data[:n_count-1]

            # Результат. Словарь первых n_count - 1.
            trimmed_data = {c_id: {'c_value': c_value, 'f_prob_value': f_prob_value} for c_id, c_value, f_prob_value in top_n}

            # Сумма f_prob_values для картегории "другие".
            other_sum = sum(x[2] for x in sorted_diagram_data[n_count-1:])

            # Добавляем картегорию "другие".
            if other_sum > 0:
                trimmed_data['other'] = {'c_value': 'Other', 'f_prob_value': other_sum}

            return trimmed_data

        # По умолчанию элементы диаграммы не подсвечены.
        self.diagram_highlight_state = False

        # Diagram data is dict where each value is dict:
        # center_id — ID центральной точки
        # c_value — Значение атрибута центральной точки. Атрибут выбран в diagram_field
        # f_prob_value — Значение вероятности, полученное в результате работы гравитационной модели
        # diagram_data = [
            # (c1_id, c1_value, f1_prob_value),
            # (c2_id, c2_value, f2_prob_value),
            # ...
            # ]
        centers_count = len(diagram_data)
        
        if centers_count == 0:
            return
        
        # Если количество центров > 6, оставить только 5 наибольших и шестую группу "[др.]".
        if centers_count > 6:
            # Сортируем список по f_prob_value по убыванию.
            sorted_data = sorted(diagram_data, key=lambda x: x[2], reverse=True)
            # Далее diagram_data содержит 6 записей.
            diagram_data = trim_n(sorted_data, 6) # + [др.]
        
        # Extract values from diagram_data
        # diagram_data is [(c1_id, c1_value, f1_prob_value), ...]
        center_ids = [item[0] for item in diagram_data]     # Список center_id
        center_values = [item[1] for item in diagram_data]  # Список значений выбранного поля центральной точки
        prob_values = [item[2] for item in diagram_data]    # Список значений вероятности. Другими словами, доли значения поля center_value в diagram_data
        prob_values_sum = sum(prob_values)
        
        # Новые названия для значений data_diagram.
        #
        u_ids = center_ids
        value_texts = center_values
        values_pct = [percentage(prob_value, prob_values_sum) for prob_value in prob_values] # Список значений вероятности в процентах
                
        # Начало создания диаграммы.
        fig, ax = plt.subplots()
        fig.subplots_adjust(**SUBPLOT_ADJUSTMENT)
        
        ax.set_title(DIAGRAM_TITLE, **DIAGRAM_TITLE_PARAMS)
        pie = ax.pie(x, **PIE_PARAMS)
        wedges = pie[0]
        
        annotations = []
        annotation_params = ANNOTATION_PARAMS

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
            
            #!! Order matters!
            format_vars = (uid_name, u_id), (value_text_name, value_text), value_pct
            # Формат вывода значений format_vars на диаграмму
            annotation_params.update(
                dict(text='\n'.join([
                        '{}: {}',
                        '{}: {}',
                        '{:.1f}%'
                    ]).format(**format_vars)
                )
            )
            
            horizontal_alignment = {-1: "right", 1: "left"}[int(np.sign(x))]
            annotation_params.update(dict(horizontalalignment=horizontal_alignment))
            
            connection_style = f"angle,angleA=0,angleB={start_angle_deg}"
            annotation_params['arrowprops'].update(dict(connectionstyle=connection_style))
            
            annotation = ax.annotate(**annotation_params)
            annotations.append(annotation)
        
        # TODO: disconnect mechanism
        fig.canvas.mpl_connect('button_press_event', lambda event: on_wedge_click(event, wedges, annotations, ON_CLICK_STYLE_PARAMS))
        return FigureCanvas(fig)
