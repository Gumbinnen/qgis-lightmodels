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

    def construct_diagram(self, diagram_data):
        # Diagram data is dict where each value is dict:
        # center_id — ID центральной точки
        # c_value — Значение атрибута центральной точки. Атрибут выбран в diagram_field
        # f_prob_value — Значение вероятности, полученное в результате работы гравитационной модели
        # diagram_data[c_id] = {c_value: f_prob_value}
        
        if len(my_dict) > 10:
            sorted_dict = dict(sorted(my_dict.items(), key=lambda x: x[1], reverse=True))
            top_n = dict(itertools.islice(sorted_dict.items(), 9))
            other_sum = sum(my_dict.values()) - sum(top_n.values())
            top_n['др.'] = other_sum
            my_dict = top_n
        
        if len(my_dict) == 0:
            return

        colors = plt.cm.tab10(np.arange(len(my_dict)))
        
        fig, ax = plt.subplots()
        ax.set_title('Распределение потребителей среди поставщиков', fontsize=10, pad=40)
        
        pie = ax.pie(my_dict.values(), startangle=90)
        
        centre_circle = plt.Circle((0, 0), 0.50, color='white', fc='white', linewidth=0)
        ax.add_artist(centre_circle)
        
        annotations = []
        wedges = pie[0]
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
            
        self.dlg_model.layout.takeAt(0).widget().deleteLater()
        canvas = FigureCanvas(fig)
        self.dlg_model.layout.addWidget(canvas)
        # выделение линий от потребителя к поставщикам
        line_layer = QgsProject.instance().mapLayersByName('линии [g. m.]')[0]
        request = QgsFeatureRequest().setFilterExpression(f'{"f_id"} = {f_id}')
        need_line_ids = [line.id() for line in line_layer.getFeatures(request)]
        line_layer.selectByIds(need_line_ids)
