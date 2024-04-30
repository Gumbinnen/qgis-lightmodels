from .colors import BLUE_PALETTES
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import numpy as np



class GravityModelDiagramManager:
    def __init__(self, parent=None):
        # TODO: USE FIELDS / PROPERTIES INSTEAD OF CONSTANS?
        AX_TITLE_PARAMS = dict(fontsize=10, pad=40)

        PIE_WEDGE_PROPS = dict(width=0.5, edgecolor='white', linewidth=1)
        PIE_PARAMS = dict(wedgeprops=PIE_WEDGE_PROPS, startangle = 0)

        ANNOTATION_TEXT_FORMAT = ' '.join(['{}: {}\n', '{}: {}\n', '{:.1f}%'])
        ANNOTATION_PARAMS = dict(arrowprops=dict(arrowstyle='-'),
                                 bbox=dict(boxstyle="square,pad=0.3",
                                           fc="w", ec="k", lw=0.72),
                                 zorder=0, va='center')

        SUBPLOT_ADJUSTMENT = dict(top=0.77, bottom=0.15, left=0.0, right=1)
        
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
        
        def on_wedge_click(event):
            def save_params(wedges):
                pass
            
            def restore_params(wedges, annotations, params):
                pass
            
            def is_click_fell_on_wedge(click_coords, wedge) -> bool:
                x, y = click_coords
                center = (0, 0)
                # Calculate the angle of the click event relative to the center of the pie chart
                angle = np.arctan2(y - center[1], x - center[0])
                # Calculate the angle of the click relative to the starting angle
                angle %= 2*np.pi  # Ensure angle is within [0, 360] degrees
                if (0 <= angle <= np.pi/2):
                    angle += 2*np.pi
                # Calculate the distance between the click event and the center of the pie chart
                distance = np.sqrt((x - center[0])**2 + (y - center[1])**2)
                
                theta1, theta2 = np.deg2rad(wedge.theta1), np.deg2rad(wedge.theta2)
                
                # TODO: Make `wedge.r + 1` a param?
                if (theta1 <= angle <= theta2) and (distance <= wedge.r + 1):
                    return True
                
                return False
            
            def highlight_wedge(wedge):
                pass
            
            def highlight_annotation(annotation):
                pass
            
            if event.inaxes != ax:
                return
            
            x, y = event.xdata, event.ydata  # Coordinates of the click event
            
            params = save_params(wedges, annotations)
            for wedge in wedges:
                hit = is_click_fell_on_wedge((x, y), wedge)

                restore_params(wedges, annotations, params)
                
                if hit:
                    highlight_wedge(wedge)
                    highlight_annotation(annotation)
                    break
            
            plt.draw()
        
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
        annotation_text = ANNOTATION_TEXT_FORMAT
        
        # Начало создания диаграммы.
        fig, ax = plt.subplots()
        
        fig.canvas.mpl_connect('button_press_event', on_wedge_click)
        fig.subplots_adjust(**subplots_adjustment)
        
        ax.set_title('Распределение потребителей среди поставщиков', **ax_title_params)
        pie = ax.pie(x, colors=colors, **pie_params)
        wedges = pie[0]        

        for wedge, u_id, value_text, value_pct in zip(wedges, u_ids, value_texts, values_pct):
            start_angle_deg = (wedge.theta1 + wedge.theta2)/2 # Mid-angle of the slice
            start_angle_rad = np.deg2rad(start_angle_deg)
            x = np.cos(start_angle_rad)
            y = np.sin(start_angle_rad)
            text_x = 1.35*np.sign(x)
            text_y = 1.4*y

            if len(value_label) > 19:
                value_label = value_label[:18]+'…'

            annotation_params = ANNOTATION_PARAMS
            horizontal_alignment = {-1: "right", 1: "left"}[int(np.sign(x))]
            annotation_params.update(dict(horizontalalignment=horizontal_alignment))
            
            connection_style = f"angle,angleA=0,angleB={start_angle_deg}"
            annotation_params['arrowprops'].update(dict(connectionstyle=connection_style))
            
            # TODO: set self.uid_name and self.value_text_name
            ax.annotate(annotation_text.format(self.uid_name, u_id, 
                                               self.value_text_name, value_text, 
                                               value_pct),
                        xy=(x, y), xytext=(text_x, text_y),
                        **annotation_params)
        
        return FigureCanvas(fig)
        #-------

        colors = plt.cm.tab10(np.arange(len(my_dict)))
        
        # как работать с numpy and mathplotlib
        fig, ax = plt.subplots()
        ax.set_title('Распределение потребителей среди поставщиков', fontsize=10, pad=40)
        
        pie = ax.pie(my_dict.values(), startangle=90)
        
        center_circle = plt.Circle((0, 0), 0.50, color='white', fc='white', linewidth=0)
        ax.add_artist(center_circle)
        
        annotations = []
        for i, (category, value) in enumerate(my_dict.items()):
            angle = pie[0][i].theta1  # Start angle of the slice
            angle += (pie[0][i].theta2 - pie[0][i].theta1) / 2 # Mid-angle of the slice
            angle_rad = np.deg2rad(angle)
            radius = 1.1  # Adjust this value to control the length of the lines
        
            x = radius * np.cos(angle_rad)
            y = radius * np.sin(angle_rad)
            
            # Adjust percentage labels
            label_x = 1.5 * np.cos(angle_rad)  # Adjust the position of the label along x-axis
            label_y = 1.5 * np.sin(angle_rad)  # Adjust the position of the label along y-axis
            percent = my_dict[category]*100
            value = str(list(my_dict.keys())[i])
            if len(value) > 19:
                value = value[:18]+'…'
            
            annotation = ax.annotate('{:.1f}%\n{}'.format(percent, value),
                        xy=(x, y), xytext=(label_x, label_y),
                        ha='center', va='center', fontsize=10, color='white',
                        arrowprops=dict(arrowstyle='-', color=colors[i]),
                        bbox=dict(boxstyle="round,pad=0.2", fc=colors[i], alpha=1.0, edgecolor='none'))
            
            annotations.append(annotation)
        
        wedges = pie[0]
        for wedge in wedges:
            wedge.set_edgecolor('white')
            wedge.set_linewidth(1)
        
        def onclick(event):
            edge_highlighed = False
            if event.inaxes == ax:
                center = (0, 0)  # Center of the pie chart
                x, y = event.xdata, event.ydata  # Coordinates of the click event
                # # Calculate the angle of the click event relative to the center of the pie chart
                angle = np.arctan2(y - center[1], x - center[0])
                # Calculate the angle of the click relative to the starting angle
                angle %= 2*np.pi  # Ensure angle is within [0, 360] degrees
                if (0 <= angle <= np.pi/2):
                    angle += 2*np.pi
                # Calculate the distance between the click event and the center of the pie chart
                distance = np.sqrt((x - center[0])**2 + (y - center[1])**2)
                # Iterate over the wedges and check if the click event falls within the boundaries of each wedge
                for i, wedge in enumerate(wedges):
                    theta1, theta2 = np.deg2rad(wedge.theta1), np.deg2rad(wedge.theta2)
                    
                    if (theta1 <= angle <= theta2) and (distance <= wedge.r + 1):
                        edge_highlighed = True
                        # Reduce alpha for all annotations and wedges
                        for annotation in annotations:
                            annotation.set_alpha(0.35)
                            # Retrieve the bounding box patch object
                            bbox_patch = annotation.get_bbox_patch()
                            r, g, b, _ = bbox_patch.get_facecolor()
                            bbox=dict(boxstyle="round,pad=0.2", fc=(r,g,b,0.35), edgecolor='none')
                            annotation.set_bbox(bbox)
                        for wedge in wedges:
                            wedge.set_alpha(0.35)
                            wedge.set_linewidth(1)
                        current_annotation = annotations[i]
                        current_wedge = wedges[i]
                        # Set alpha to 1 for the clicked annotation and wedge
                        current_annotation.set_alpha(1)
                        current_annotation.set_zorder(12)
                        bbox_patch = current_annotation.get_bbox_patch()
                        r, g, b, _ = bbox_patch.get_facecolor()
                        bbox=dict(boxstyle="round,pad=0.2", fc=(r,g,b,1), edgecolor='none')
                        current_annotation.set_bbox(bbox)
                        current_wedge.set_alpha(1)
                        # Add white border to the clicked wedge
                        current_wedge.set_linewidth(2)
                        plt.draw()
                        break  # Exit loop once a wedge is found
                        
            if not edge_highlighed:
                for annotation in annotations:
                    annotation.set_alpha(1)
                    # Retrieve the bounding box patch object
                    bbox_patch = annotation.get_bbox_patch()
                    r, g, b, _ = bbox_patch.get_facecolor()
                    bbox=dict(boxstyle="round,pad=0.2", fc=(r,g,b,1), edgecolor='none')
                    annotation.set_bbox(bbox)
                for wedge in wedges:
                    wedge.set_alpha(1)
                    wedge.set_linewidth(1)
                plt.draw()
        
        fig.canvas.mpl_connect('button_press_event', onclick)
        
        fig.subplots_adjust(top=0.77, bottom=0.15, left=0.0, right=1)
        
        return FigureCanvas(fig)
