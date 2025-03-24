import sys
import os
from pathlib import Path

import pandas as pd
import fitz

from PyQt6.QtCore import Qt, QSize, QPointF, QPoint, QRectF, QRect, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, QFileDialog, QVBoxLayout, QHBoxLayout,
                             QWidget, QSpinBox, QGraphicsItem, QGraphicsScene, QGraphicsWidget, QToolBar, QGraphicsView,
                             QGraphicsRectItem, QStatusBar, QMenu, QDialog, QLineEdit, QInputDialog, QGridLayout,
                             QFrame, QGraphicsLineItem, QTabWidget, QSpacerItem, QComboBox)
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPen, QPainter, QColor, QPolygonF, QMouseEvent, QCursor

'''
((1)) Custom GraphicsView to integrate into main window
'''
class GraphicsView(QGraphicsView):
    mouse_pressed_signal = pyqtSignal(QPoint)  # <- this enables sending the cursor position to the main window

    def __init__(self, scene):
        super().__init__(scene)

        self.is_pressed = False
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setFocusPolicy(
            Qt.FocusPolicy.NoFocus)  # <- this is needed so that rectangle positions may be adjusted via arrow keys

    ## Below are functions to navigate the viewer (zoom in and out of scene, drag around)
    def wheelEvent(self, event):
            angle = event.angleDelta().y()
            if angle > 0:
                self.scale(1.2, 1.2)  # Zoom in sensitivity
            else:
                self.scale(1 / 1.2, 1 / 1.2)  # Zoom out sensitivity
            event.accept()

    ## Alternative to the wheelEvent from above, where zooming in and out only functions with the ctrl-modifier
    # def wheelEvent(self, event):
    #     if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
    #         angle = event.angleDelta().y()
    #         if angle > 0:
    #             self.scale(1.2, 1.2)  # Zoom in sensitivity
    #         else:
    #             self.scale(1 / 1.2, 1 / 1.2)  # Zoom out sensitivity
    #         event.accept()
    #     else: super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_pressed = True
            self.mouse_pressed_signal.emit(event.pos())

        if event.button() == Qt.MouseButton.RightButton:
            self.mouse_pressed_signal.emit(event.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self.mouse_pressed_signal.emit(event.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_pressed = False
            self.mouse_pressed_signal.emit(event.pos())

        if event.button() == Qt.MouseButton.RightButton:
            self.mouse_pressed_signal.emit(event.pos())
        super().mouseReleaseEvent(event)

'''
((2)) Main Window
'''
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # create temp folder in directory of app unless it already exists
        if not os.path.exists('temp'):
            os.makedirs('temp')

        '''
        ((2.0)) Data storage and stuff
        '''
        ## Dictionaries that store all items within the scene
        self.item_dict = dict()  # <- for annotations
        self.item_coords = dict()  # <- for coordinates and shape of items
        self.item_colors = dict()  # <- this stores the color of each item
        self.item_anchors = dict()  # <- this stores the baselines of each item
        self.item_index = dict()  # <- for item index

        self.item_counter = 1

        self.page_index = dict()

        ## List that stores all annotation layers
        self.annotation_layers = dict()
        self.annotation_layers['Dims'] = []
        self.dim_counter = 1

        self.current_key = 'Dims'
        self.current_color = None

        # dictionary that - for each page - stores all items placed on the page
        self.page_items = dict()
        self.page_items[1] = []

        '''
        ((2.1)) Layout
        '''
        ## Mouse tracking stuff
        self.last_pos = QPoint()
        self.scene_pos = QPoint()

        ## General Main Window and Layout settings
        self.setWindowTitle('HAnnoI: Handwriting Annotation Interface')
        self.resize(1080, 720)

        menu = self.menuBar()
        menu.setNativeMenuBar(False)

        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.context_menu = QMenu()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # item (i.e. rectangle) settings
        self.rect_x = QSpinBox()  # for width
        self.rect_x.setValue(50)
        self.rect_x.setMaximum(1000)
        self.rect_x.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        rect_width = QLabel('Width of new item:')
        rect_width.setAlignment(Qt.AlignmentFlag.AlignRight)
        rect_width.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.rect_y = QSpinBox()  # for height
        self.rect_y.setValue(50)
        self.rect_y.setMaximum(1000)
        self.rect_y.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        rect_height = QLabel('Height of new item:')
        rect_height.setAlignment(Qt.AlignmentFlag.AlignRight)
        rect_height.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.rect_col = QComboBox()  # for color
        self.rect_col.addItems(['red', 'green', 'blue'])
        self.rect_col.currentIndexChanged.connect(self.setColor)
        rect_colLab = QLabel('Color:')
        rect_colLab.setAlignment(Qt.AlignmentFlag.AlignRight)
        rect_colLab.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.rect_pen = QPen(Qt.GlobalColor.red)
        self.rect_pen.setWidth(1)

        # establish scene in which the to be annotated document is displayed / items for annotation are placed in
        self.scene = QGraphicsScene(0, 0, 0, 0)
        self.view = GraphicsView(self.scene)
        self.view.mouse_pressed_signal.connect(self.mouseTracker)

        # per default one tab; additional tabs are added to match page count of loaded document
        self.view_tabs = QTabWidget()
        self.view_tabs.setTabPosition(QTabWidget.TabPosition.West)
        self.view_tabs.addTab(self.view, 'Page 1')

        self.view_tabs.currentChanged.connect(self.changePage)  # <- triggers when changing current tab

        # set up grid layout for graphical side of application (mainly picture and item display)
        view_layout = QGridLayout()
        view_layout.addWidget(rect_width, 0, 10)
        view_layout.addWidget(self.rect_x, 0, 11)
        view_layout.addWidget(rect_height, 0, 12)
        view_layout.addWidget(self.rect_y, 0, 13)
        view_layout.addWidget(rect_colLab, 0, 14)
        view_layout.addWidget(self.rect_col, 0, 15)
        view_layout.setColumnMinimumWidth(13, 10)

        view_layout.addWidget(self.view_tabs, 1, 0, 1, 16)

        view_widget = QWidget()
        view_widget.setLayout(view_layout)
        view_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # <- this line enables adjusting the position of
                                                                # rectangles via arrow keys; additionally, the focus
                                                                # within the GraphicsView class must be set to NoFocus

        ## Widget for the annotations
        # TOP WIDGET
        anno_top_widget = QGridLayout()

        self.anno_sheetLab = QPushButton('Document:')
        self.anno_sheetTxt = QLabel('No document/image loaded')

        self.anno_pageLab = QPushButton('Page number:')
        self.anno_pageTxt = QLabel('No document/image loaded')

        self.anno_indexLab = QPushButton('Item index:')
        self.anno_indexLab.setStatusTip('Change index of currently selected item')
        self.anno_indexTxt = QLabel('No item selected')

        self.anno_coordLab = QPushButton('Coordinates:')
        self.anno_coordTxt = QLabel('No item selected')

        self.anno_anchorLab = QPushButton('Anchor:')
        self.anno_anchorTxt = QLabel('No item selected')

        # self.anno_pageLab.pressed.connect(self.change_page)
        self.anno_indexLab.pressed.connect(self.updateIndex)

        anno_top_widget.addWidget(self.anno_sheetLab, 0, 0)
        anno_top_widget.addWidget(self.anno_sheetTxt, 0, 1)
        anno_top_widget.addWidget(self.anno_pageLab, 1, 0)
        anno_top_widget.addWidget(self.anno_pageTxt, 1, 1)
        anno_top_widget.addWidget(self.anno_indexLab, 2, 0)
        anno_top_widget.addWidget(self.anno_indexTxt, 2, 1)
        anno_top_widget.addWidget(self.anno_coordLab, 3, 0)
        anno_top_widget.addWidget(self.anno_coordTxt, 3, 1)
        anno_top_widget.addWidget(self.anno_anchorLab, 4, 0)
        anno_top_widget.addWidget(self.anno_anchorTxt, 4, 1)

        anno_title = QLabel('Annotation Layers')
        self.anno_new_layer_title = QLineEdit()
        self.anno_new_layer_title.setPlaceholderText('Enter new label')
        anno_top_widget.addWidget(anno_title, 5, 0, 1, 2)
        anno_top_widget.addWidget(self.anno_new_layer_title, 6, 0, 1, 2)

        # BOT WIDGET
        self.anno_bot_widget = QHBoxLayout()
        self.anno_bot_widgetLabs = QVBoxLayout()
        self.anno_bot_widgetLabs.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.anno_bot_widgetTxts = QVBoxLayout()
        self.anno_bot_widgetTxts.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.anno_bot_widget.addLayout(self.anno_bot_widgetLabs)
        self.anno_bot_widget.addLayout(self.anno_bot_widgetTxts)
        self.annotations = QWidget()
        self.annotations.setLayout(self.anno_bot_widget)

        # TOP AND BOT COMBINED
        anno_full = QVBoxLayout()
        anno_full.addLayout(anno_top_widget, stretch=1)
        anno_full.addWidget(self.annotations, stretch=4)

        # FINAL LAYOUT
        main_layout = QHBoxLayout()
        main_layout.addWidget(view_widget, stretch=5)
        main_layout.addLayout(anno_full, stretch=2)

        container = QWidget()
        container.setLayout(main_layout)

        self.setCentralWidget(container)

        '''
        ((2.2)) Actions (mainly SIGNALS that trigger some function)
        '''
        # Toolbar + Context Menu Actions (== Signals for Slots)
        image_action = QAction('Single Image', self)
        image_action.setStatusTip('Import single image for annotation')
        image_action.triggered.connect(self.imgImport)

        pdf_action = QAction('From PDF', self)
        pdf_action.setStatusTip('Import images from PDF file')
        pdf_action.triggered.connect(self.pdfImport)

        new_menu = menu.addMenu('New')
        new_menu.addAction(image_action)
        new_menu.addAction(pdf_action)

        csv_action = QAction('Import CSV', self)
        csv_action.setStatusTip('Import CSV to continue working')
        csv_action.triggered.connect(self.csvImport)

        scheme_action = QAction('Import Scheme', self)
        scheme_action.setStatusTip('Import annotation scheme from CSV file')
        scheme_action.triggered.connect(self.schemeImport)

        import_menu = menu.addMenu('Import')
        import_menu.addAction(csv_action)
        import_menu.addAction(scheme_action)

        export_action = QAction('Export', self)
        export_action.setStatusTip('Export all annotations to CSV file')
        export_action.triggered.connect(self.exportAnnotations)
        menu.addAction(export_action)

        screenshot_action = QAction('Render', self)
        screenshot_action.setStatusTip('Render screenshots')
        screenshot_action.triggered.connect(self.takeScreenshots)
        menu.addAction(screenshot_action)

        add_action = QAction('Add Item', self)
        add_action.setStatusTip('Add item to current page')
        add_action.setShortcut('Ctrl+R')
        add_action.triggered.connect(self.addItem)
        toolbar.addAction(add_action)
        self.context_menu.addAction(add_action)

        change_action = QAction('Adjust Item', self)
        change_action.setStatusTip('Change size of currently selected item')
        change_action.triggered.connect(self.adjustItem)
        toolbar.addAction(change_action)

        delete_action = QAction('Delete Item', self)
        delete_action.setStatusTip('Delete currently selected item')
        delete_action.triggered.connect(self.deleteItem)
        toolbar.addAction(delete_action)

        self.toggle_action = QAction('Toggle Immovable', self)
        self.toggle_action.setStatusTip('Toggle immovable')
        self.toggle_action.setCheckable(True)
        self.toggle_action.triggered.connect(self.toggleItems)
        toolbar.addAction(self.toggle_action)

        self.recolor_action = QAction('Recolor Mode', self)
        self.recolor_action.setStatusTip('Toggle item recoloring mode')
        self.recolor_action.setCheckable(True)
        toolbar.addAction(self.recolor_action)

        # this Signal triggers updating all annotation input lines to match the currently selected rectangle:
        self.scene.selectionChanged.connect(self.changeKey)
        self.anchorStatus = False

    '''
    ((3)) CUSTOM FUNCTIONS
    '''

    '''
    ((3.1)) Import functions (single image, PDF,  CSV, annotation scheme)
    '''
    # load single image for annotation (CURRENTLY NOT IN USE)
    def imgImport(self):
        self.scene.clearSelection()
        self.view_tabs.setCurrentIndex(0)

        fname = QFileDialog.getOpenFileName(self, 'Open Image', './', '(*.png *.jpg *.jpeg *.bmp)',)

        self.anno_sheetTxt.setText('No document/image loaded')
        self.anno_pageTxt.setText('No document/image loaded')

        if len(fname[0]) > 0:
            self.scene.clear()
            self.clearDictionaries()
            self.clearAnnotationTab()

            # remove all view tabs but the first one:
            for i in reversed(range(list(self.page_items.keys())[-1])):
                if i == 0: break
                else: self.view_tabs.removeTab(i)

            self.page_index = dict()
            self.page_items = dict()

            # clear temp folder to avoid conflicts
            temp_path = Path('./temp')
            for temp_file in temp_path.iterdir():
                if temp_file.is_file(): temp_file.unlink()

            file = fname[0].split('/')
            self.anno_sheetTxt.setText(file[-1])  # <- adds name of current work sheet to program
            self.anno_pageTxt.setText(str(1))

            self.scene.addPixmap(QPixmap(fname[0]))
            self.scene.items()[0].setZValue(1)

            self.page_index[fname[0]] = 1
            self.page_items[1] = []

    # load in PDF file to annotate all pages
    def pdfImport(self):
        self.scene.clearSelection()
        self.view_tabs.setCurrentIndex(0)

        fname = QFileDialog.getOpenFileName(self, 'Open Image', './', '(*.pdf)',)

        if len(fname[0]) > 0:
            # STEP 1: CLEAR EVERYTHING
            self.scene.clear()
            self.clearDictionaries()
            self.clearAnnotationTab()
        else: return

        # remove all view tabs but the first one:
        for i in reversed(range(list(self.page_items.keys())[-1])):
            if i == 0: break
            else: self.view_tabs.removeTab(i)

        self.page_index = dict()
        self.page_items = dict()

        # clear temp folder to avoid conflicts
        temp_path = Path('./temp')
        for temp_file in temp_path.iterdir():
            if temp_file.is_file(): temp_file.unlink()

        # STEP 2: PROCESS PDF FILE
        file = fname[0].split('/')
        self.anno_sheetTxt.setText(file[-1])  # <- adds name of current work sheet to program

        pdf_file = fitz.open(fname[0])

        for i in range(len(pdf_file)):
            page = pdf_file.load_page(i)  # load the page
            image = page.get_images(full=True)  # get images on the page

            xref = image[0][0]

            base_image = pdf_file.extract_image(xref)
            image_bytes = base_image['image']
            image_ext = base_image['ext']

            image_name = file[-1] + '_page_' + str(i + 1) + '.' + image_ext

            self.page_index[image_name] = i + 1

            with open('temp/' + image_name, 'wb') as image_file:
                image_file.write(image_bytes)

        current_page = list(self.page_index.keys())[0]
        self.scene.addPixmap(QPixmap('temp/' + current_page))
        self.scene.items()[0].setZValue(1)

        self.anno_pageTxt.setText(str(self.page_index[current_page]))

        # this adds one GraphicsView tab for each page beyond the first
        self.page_items[1] = []
        for i in range(len(self.page_index) - 1):
            new_view = GraphicsView(self.scene)
            new_view.mouse_pressed_signal.connect(self.mouseTracker)
            self.view_tabs.addTab(new_view, 'Page ' + str(i + 2))

            self.page_items[i + 2] = []

    # load in CSV file to continue annotating
    def csvImport(self):
        self.scene.clearSelection()
        self.view_tabs.setCurrentIndex(0)

        # STEP 1: GET CSV FILE
        fname = QFileDialog.getOpenFileName(
            self,
            'Open CSV File', './', '(*.csv)', )

        if len(fname[0]) > 0:
            # load in data frame
            df = pd.read_csv(fname[0])

            # get some file and path info
            file_csv = fname[0].split('/')[-1]  # name of csv file
            file_doc = df['Source'][0]  # name of image file
            file_path = fname[0].replace(file_csv, '')
        else: return

        # STEP 2: CLEAN UP EVERYTHING CURRENTLY LOADED
        # this branch is for importing a single image
        if file_doc.split('.')[-1] != 'pdf':
            self.findFile('Single Image')
            self.imgImport()

        # this branch is for importing multiple images from a pdf file; the code will skip to STEP 4 otherwise
        else:
            self.scene.clear()
            self.clearDictionaries()
            self.clearAnnotationTab()

            # remove all view tabs but the first one:
            for i in reversed(range(list(self.page_items.keys())[-1])):
                if i == 0: break
                else: self.view_tabs.removeTab(i)

            self.page_index = dict()
            self.page_items = dict()

            # clear temp folder to avoid conflicts
            temp_path = Path('./temp')
            for temp_file in temp_path.iterdir():
                if temp_file.is_file(): temp_file.unlink()

            # STEP 3: IMPORT CSV AND IMPORT PICTURE(S) INTO SCENE (AND ADD ONE TAB PER PICTURE)
            self.anno_sheetTxt.setText(file_doc)

            try: fitz.open(file_path + '/' + file_doc)
            except: pdf_file = self.findFile(file_path) # <- opens new window to select PDF if not in folder of CSV file
            else: pdf_file = fitz.open(file_path + '/' + file_doc)

            for i in range(len(pdf_file)):
                page = pdf_file.load_page(i)  # load the page
                image = page.get_images(full=True)  # get images on the page

                xref = image[0][0]

                base_image = pdf_file.extract_image(xref)
                image_bytes = base_image['image']
                image_ext = base_image['ext']

                image_name = file_doc + '_page_' + str(i + 1) + '.' + image_ext

                self.page_index[image_name] = i + 1

                with open('temp/' + image_name, 'wb') as image_file:
                    image_file.write(image_bytes)

            current_page = list(self.page_index.keys())[0]
            self.scene.addPixmap(QPixmap('temp/' + current_page))
            self.scene.items()[0].setZValue(1)

            self.anno_pageTxt.setText(str(self.page_index[current_page]))

            # this adds one GraphicsView tab for each page beyond the first
            self.page_items[1] = []
            for i in range(len(self.page_index) - 1):
                new_view = GraphicsView(self.scene)
                new_view.mouse_pressed_signal.connect(self.mouseTracker)
                self.view_tabs.addTab(new_view, 'Page ' + str(i + 2))

                self.page_items[i + 2] = []

        # STEP 4: LOAD IN ANNOTATION WIDGET (if a single image was selected, the code immediately continues here)
        for col in df.columns[6:]:
            new_dim = col
            self.annotation_layers['Dims'].append(new_dim)

            for key in self.item_dict.keys():
                self.item_dict[key].append(new_dim)

            self.anno_bot_widgetLabs.addWidget(QPushButton(new_dim))
            self.anno_bot_widgetLabs.itemAt(self.dim_counter - 1).widget().setFixedHeight(30)
            self.anno_bot_widgetLabs.itemAt(self.dim_counter - 1).widget().pressed.connect(self.editLayer)

            self.anno_bot_widgetTxts.addWidget(QLineEdit(new_dim))
            self.anno_bot_widgetTxts.itemAt(self.dim_counter - 1).widget().setFixedHeight(30)
            self.anno_bot_widgetTxts.itemAt(self.dim_counter - 1).widget().setPlaceholderText('NA')
            self.anno_bot_widgetTxts.itemAt(self.dim_counter - 1).widget().textChanged.connect(self.updateAnnotations)

            self.dim_counter += 1

        # # STEP 5: LOAD IN RECTANGLES AND ANNOTATIONS
        pen = QPen(Qt.GlobalColor.red)
        pen.setWidth(1)

        for i in df['Index']:

            # 5.1: coordinates + rectangles
            current_coords = df.loc[df['Index'].isin([i]), 'Coordinates'].tolist()[0][1:-1].split(', ')
            x, y = float(current_coords[0]), float(current_coords[1])
            width, height = float(current_coords[2]), float(current_coords[3])

            rect = QGraphicsRectItem(0, 0, width, height)
            rect.setPos(x, y)
            rect.setPen(pen)

            self.scene.addItem(rect)

            self.item_dict[rect] = []
            self.item_coords[rect] = [round(rect.x(), 2),
                                      round(rect.y(), 2),
                                      rect.rect().width(),
                                      rect.rect().height()]

            # 5.2: item index and page
            self.item_index[rect] = i

            current_page = df.loc[df['Index'].isin([i]), 'Page'].tolist()[0]
            self.page_items[current_page].append(rect)

            # 5.3: item color
            current_color = df.loc[df['Index'].isin([i]), 'Color'].tolist()[0]
            self.item_colors[rect] = current_color
            if current_color == 'red': rect.setPen(QPen(Qt.GlobalColor.red))
            elif current_color == 'green': rect.setPen(QPen(Qt.GlobalColor.green))
            elif current_color == 'blue': rect.setPen(QPen(Qt.GlobalColor.blue))

            # 5.4: anchors
            current_anchor = df.loc[df['Index'].isin([i]), 'Anchor'].tolist()[0]
            if pd.isna(current_anchor): self.item_anchors[rect] = None
            else:
                x, y = current_anchor[1:-1].split(', ')
                self.item_anchors[rect] = [float(x), float(y)]

            # 5.5: annotations
            vals = df.loc[df['Index'].isin([i]), df.columns[6:]].values.flatten().tolist()

            for v in range(len(vals)):
                if pd.isna(vals[v]): vals[v] = ''
            self.item_dict[rect] = vals

            self.item_counter = i

        self.item_counter += 1

        if file_doc.split('.')[-1] == 'pdf': self.changePage()
        else:
            self.scene.items()[0].setZValue(1)
            for item in self.page_items[1]:
                item.setZValue(2)
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            self.toggleItems()

    # opens a dialog that tells the user to select an image or PDF corresponding to the to be imported CSV file
    def findFile(self, path):
        if path == 'Single Image':
            alert = QDialog(self)
            alert.setWindowTitle('Select Image File')
            layout = QVBoxLayout()
            layout.addWidget(QLabel('Please select the corresponding image file.'))
            confirm_button = QPushButton('Confirm')
            confirm_button.pressed.connect(alert.accept)
            layout.addWidget(confirm_button)
            alert.setLayout(layout)
            alert.exec()
        else:
            alert = QDialog(self)
            alert.setWindowTitle('Select PDF File')
            layout = QVBoxLayout()
            layout.addWidget(QLabel('PDF not in folder of CSV.\nPlease select corresponding PDF file.'))
            confirm_button = QPushButton('Confirm')
            confirm_button.pressed.connect(alert.accept)
            layout.addWidget(confirm_button)
            alert.setLayout(layout)
            alert.exec()

            alt = QFileDialog.getOpenFileName(self, 'Select Corresponding PDF File', path, '(*.pdf)', )
            return fitz.open(alt[0])

    # this function imports custom annotation layers (i.e. columns) from a CSV file
    def schemeImport(self):
        # STEP 1: GET CSV FILE
        fname = QFileDialog.getOpenFileName(
            self,
            'Open CSV File', './', '(*.csv)', )

        if len(fname[0]) > 0:
            # load in data frame
            df = pd.read_csv(fname[0])
        else: return

        for col in df.columns[6:]:
            new_dim = col
            self.annotation_layers['Dims'].append(new_dim)

            for key in self.item_dict.keys():
                self.item_dict[key].append("")

            self.anno_bot_widgetLabs.addWidget(QPushButton(new_dim))
            self.anno_bot_widgetLabs.itemAt(self.dim_counter - 1).widget().setFixedHeight(30)
            self.anno_bot_widgetLabs.itemAt(self.dim_counter - 1).widget().pressed.connect(self.editLayer)

            self.anno_bot_widgetTxts.addWidget(QLineEdit(new_dim))
            self.anno_bot_widgetTxts.itemAt(self.dim_counter - 1).widget().setFixedHeight(30)
            self.anno_bot_widgetTxts.itemAt(self.dim_counter - 1).widget().setPlaceholderText('NA')
            self.anno_bot_widgetTxts.itemAt(self.dim_counter - 1).widget().textChanged.connect(self.updateAnnotations)

            self.dim_counter += 1

    '''
    ((3.2)) Functions for actions within the scene
    '''
    # loads in a new page if the corresponding tab is selected
    def changePage(self):
        self.scene.clearSelection()

        current_index = self.view_tabs.currentIndex()

        for item in self.scene.items():
            if item.zValue() == 1:
                self.scene.removeItem(item)
            else:
                item.setZValue(0)
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

        current_page = list(self.page_index.keys())[current_index]

        self.scene.addPixmap(QPixmap('temp/' + current_page))
        self.scene.items()[0].setZValue(1)

        self.anno_pageTxt.setText(str(self.page_index[current_page]))

        for item in self.page_items[current_index + 1]:
            item.setZValue(2)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

        self.toggleItems()

    # this function triggers whenever an item in the scene is selected/deselected and does several things:
    # 1) loads and displays annotations of selected item
    # 2) makes selected item transparent
    # 3) shows anchor of selected item
    def changeKey(self):
        if self.anchorStatus == True:
            self.scene.removeItem(self.anchor)
            self.anchorStatus = False

        ## this triggers whenever a rectangle is selected:
        if len(self.scene.selectedItems()) == 1:

            if self.current_key != self.scene.selectedItems()[0] and self.current_key != 'Dims':
                if not self.recolor_action.isChecked():
                    if self.current_color == 'red': pen = QPen(Qt.GlobalColor.red)
                    elif self.current_color == 'green': pen = QPen(Qt.GlobalColor.green)
                    elif self.current_color == 'blue': pen = QPen(Qt.GlobalColor.blue)
                    self.current_key.setPen(pen)
                else:
                    self.current_key.setPen(self.rect_pen)
                    self.item_colors[self.current_key] = self.rect_col.currentText()

            self.current_key = self.scene.selectedItems()[0]
            self.current_color = self.item_colors[self.current_key]

            pen = QPen(Qt.GlobalColor.transparent)
            self.current_key.setPen(pen)
            self.current_key.setPos(self.current_key.pos())

            widgets = self.anno_bot_widgetTxts.count()
            for i in range(widgets):
                self.anno_bot_widgetTxts.removeWidget(self.anno_bot_widgetTxts.itemAt(0).widget())

            for i in range(len(self.item_dict[self.current_key])):
                self.anno_bot_widgetTxts.addWidget(QLineEdit(str(self.item_dict[self.current_key][i])))
                self.anno_bot_widgetTxts.itemAt(i).widget().setPlaceholderText('NA')
                self.anno_bot_widgetTxts.itemAt(i).widget().setFixedHeight(30)
                self.anno_bot_widgetTxts.itemAt(i).widget().textChanged.connect(self.updateAnnotations)

            self.anno_coordTxt.setText(str(self.item_coords[self.current_key]))
            self.anno_indexTxt.setText(str(self.item_index[self.current_key]))
            self.anno_anchorTxt.setText(str(self.item_anchors[self.current_key]))

            if self.item_anchors[self.current_key] is not None:
                self.anchor = QGraphicsLineItem(self.item_anchors[self.current_key][0] - 5,
                                                self.item_anchors[self.current_key][1],
                                                self.item_anchors[self.current_key][0] + 5,
                                                self.item_anchors[self.current_key][1])

                pen = QPen(Qt.GlobalColor.green)
                pen.setWidth(1)
                pen.setStyle(Qt.PenStyle.DashLine)
                self.anchor.setPen(pen)
                self.anchor.setZValue(3)

                self.scene.addItem(self.anchor)

                self.anchorStatus = True

        ## this triggers whenever a rectangle is de-selected (i.e. nothing is selected):
        else:
            if self.current_key != 'Dims':
                if not self.recolor_action.isChecked():
                    if self.current_color == 'red': pen = QPen(Qt.GlobalColor.red)
                    elif self.current_color == 'green': pen = QPen(Qt.GlobalColor.green)
                    elif self.current_color == 'blue': pen = QPen(Qt.GlobalColor.blue)
                    self.current_key.setPen(pen)
                else:
                    self.current_key.setPen(self.rect_pen)
                    self.item_colors[self.current_key] = self.rect_col.currentText()

            self.current_key = 'Dims'

            widgets = self.anno_bot_widgetTxts.count()
            for i in range(widgets):
                self.anno_bot_widgetTxts.removeWidget(self.anno_bot_widgetTxts.itemAt(0).widget())

            for i in range(len(self.annotation_layers[self.current_key])):
                self.anno_bot_widgetTxts.addWidget(QLineEdit(self.annotation_layers[self.current_key][i]))
                self.anno_bot_widgetTxts.itemAt(i).widget().setFixedHeight(30)

            self.anno_indexTxt.setText('No item selected')
            self.anno_coordTxt.setText('No item selected')
            self.anno_anchorTxt.setText('No item selected')

    '''
    ((3.3)) Functions that handle items in the scene
    '''
    # function to set color of rectangles
    def setColor(self, pen):
        if pen == 0: self.rect_pen = QPen(Qt.GlobalColor.red)
        elif pen == 1: self.rect_pen = QPen(Qt.GlobalColor.green)
        elif pen == 2: self.rect_pen = QPen(Qt.GlobalColor.blue)

    # add item to scene and create corresponding entry in dictionary
    def addItem(self):
        rect = QGraphicsRectItem(0, 0, int(self.rect_x.text()), int(self.rect_y.text()))

        # this makes it so that the center of the new rectangle aligns with where the mouse click happened
        rect.setPos(self.scene_pos.x() - int(self.rect_x.text()) / 2,
                    self.scene_pos.y() - int(self.rect_y.text()) / 2)

        rect.setPen(self.rect_pen)
        rect.setZValue(2)

        # make rectangles movable and selectable
        rect.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

        # only rectangles with a size of at least 1x1 pixels are added
        if int(self.rect_x.text()) > 0 and int(self.rect_y.text()) > 0:
            self.scene.addItem(rect)

            # add new rectangle to dictionary
            self.item_dict[rect] = []
            for i in range(self.dim_counter - 1):
                self.item_dict[rect].append('')

            # add coordinates/size of new rectangle to corresponding dictionary
            self.item_coords[rect] = [round(rect.x(), 2), round(rect.y(), 2), rect.rect().width(), rect.rect().height()]
            self.item_colors[rect] = self.rect_col.currentText()
            self.item_anchors[rect] = None
            self.item_index[rect] = self.item_counter
            self.item_counter += 1

            # add rectangle to page dictionary
            self.page_items[self.view_tabs.currentIndex() + 1].append(rect)

            # the part below ensures that the newly added rectangle gets selected right away (while other are not selected)
            # the keyPressEvent function below allows for immediate adjustments to newly added rectangle via arrow keys
            for item in self.scene.items():
                item.setSelected(False)
            rect.setSelected(True)

    # change size of rectangle
    def adjustItem(self):
        item = self.scene.selectedItems()
        if len(item) > 0:
            item[0].setRect(0, 0, int(self.rect_x.text()), int(self.rect_y.text()))

            # update coordinates dictionary:
            self.item_coords[item[0]] = [round(item[0].x(), 2),
                                         round(item[0].y(), 2),
                                         item[0].rect().width(),
                                         item[0].rect().height()]
            self.anno_coordTxt.setText(str(self.item_coords[self.current_key]))

    # this function is for resizing items with the mouse
    def resizeItem(self, x, y):
        item = self.scene.selectedItems()
        if len(item) == 1:
            width_change = item[0].x() - x
            height_change = item[0].y() - y

            new_width = item[0].rect().width() - width_change
            new_height = item[0].rect().height() - height_change

            # only resize if new width and height is above 0:
            if int(new_width) > 0 and int(new_height) > 0:
                item[0].setRect(0, 0, int(new_width), int(new_height))

            # update coordinates dictionary:
            self.item_coords[item[0]] = [round(item[0].x(), 2),
                                         round(item[0].y(), 2),
                                         item[0].rect().width(),
                                         item[0].rect().height()]
            self.anno_coordTxt.setText(str(self.item_coords[self.current_key]))

    # delete currently selected item (and update dictionaries accordingly)
    def deleteItem(self):
        if self.current_key != 'Dims':

            self.item_dict.pop(self.current_key)
            self.item_coords.pop(self.current_key)
            self.item_anchors.pop(self.current_key)

            current_index = self.item_index[self.current_key]

            self.item_index.pop(self.current_key)
            self.item_counter -= 1

            for key in self.item_index.keys():
                if self.item_index[key] > current_index:
                    self.item_index[key] -= 1

            self.page_items[self.view_tabs.currentIndex() + 1].remove(self.current_key)

            self.scene.removeItem(self.current_key)

            self.scene.clearSelection()

    # changes movable status of items in the scene
    def toggleItems(self):
        if self.toggle_action.isChecked():
            for key in self.item_index.keys():
                key.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        else:
            for key in self.item_index.keys():
                key.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

    # this functions marks the line on which the annotated letter is written
    def setAnchor(self):
        item = self.scene.selectedItems()

        if self.anchorStatus == True:
            self.scene.removeItem(self.anchor)
            self.anchorStatus = False

        x = self.item_coords[item[0]][0] + self.item_coords[item[0]][2] / 2
        y = self.item_coords[item[0]][1] + self.item_coords[item[0]][3]

        self.anchor = QGraphicsLineItem(x - 5, y, x + 5, y)

        self.item_anchors[item[0]] = [round(x, 2), round(y, 2)]
        self.anno_anchorTxt.setText(str(self.item_anchors[item[0]]))

        pen = QPen(Qt.GlobalColor.green)
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DashLine)
        self.anchor.setPen(pen)
        self.anchor.setZValue(3)

        self.scene.addItem(self.anchor)

        self.anchorStatus = True

    '''
    ((3.4)) Annotation functions
    '''
    # this opens a dialog box to modify the index of the currently selected rectangle
    def updateIndex(self):
        if len(self.scene.selectedItems()) == 1:
            index_dialog = QDialog(self)
            index_dialog.setWindowTitle('Set index of current item')

            layout = QVBoxLayout()
            layout.addWidget(QLabel(
                'Change index of current item.\nAdjusts index of other items accordingly.'))
            layout.addWidget(QLabel('Current index: ' + str(self.item_index[self.current_key])))

            values = list()
            for value in self.item_index.values():
                values.append(value)

            self.new_index = QSpinBox()
            self.new_index.setMinimum(1)
            self.new_index.setMaximum(max(values))
            self.new_index.setValue(self.item_index[self.current_key])
            confirm_button = QPushButton('Confirm')
            confirm_button.pressed.connect(self.indexLoop)
            confirm_button.pressed.connect(index_dialog.accept)

            layout.addWidget(self.new_index)
            layout.addWidget(confirm_button)

            index_dialog.setLayout(layout)
            index_dialog.exec()
        else:
            print('No Item selected')

    # this adjusts all indices depending on the new index of the currently selected item
    def indexLoop(self):
        current_index = self.item_index[self.current_key]

        if current_index == self.new_index.value():
            self.status_bar.showMessage('Nothing changed', 3000)

        elif current_index > self.new_index.value():
            for key in self.item_index.keys():
                if self.item_index[key] >= self.new_index.value() and self.item_index[key] < current_index:
                    self.item_index[key] = self.item_index[key] + 1

            self.item_index[self.current_key] = self.new_index.value()

        elif current_index < self.new_index.value():
            for key in self.item_index.keys():
                if self.item_index[key] <= self.new_index.value() and self.item_index[key] > current_index:
                    self.item_index[key] = self.item_index[key] - 1

            self.item_index[self.current_key] = self.new_index.value()

        self.anno_indexTxt.setText(str(self.item_index[self.current_key]))

    # add annotation layers
    def addAnnotationLayer(self):
        self.scene.clearSelection()
        new_dim = self.anno_new_layer_title.text()

        # add new layer to list of all annotation layers;
        # this is important as newly added rectangles are assigned with all previously added layers via this list
        self.annotation_layers['Dims'].append(new_dim)

        # add new annotation layer to all already existing rectangles
        for key in self.item_dict.keys():
            self.item_dict[key].append('')

        # create widgets to add to annotation layers
        self.anno_bot_widgetLabs.addWidget(QPushButton(new_dim))
        self.anno_bot_widgetLabs.itemAt(self.dim_counter - 1).widget().setFixedHeight(30)
        self.anno_bot_widgetLabs.itemAt(self.dim_counter - 1).widget().pressed.connect(self.editLayer)

        # this part triggers changes to item specific annotations
        self.anno_bot_widgetTxts.addWidget(QLineEdit(new_dim))
        self.anno_bot_widgetTxts.itemAt(self.dim_counter - 1).widget().setFixedHeight(30)
        self.anno_bot_widgetTxts.itemAt(self.dim_counter - 1).widget().setPlaceholderText('NA')
        self.anno_bot_widgetTxts.itemAt(self.dim_counter - 1).widget().textChanged.connect(self.updateAnnotations)
        self.dim_counter += 1

    # opens dialog for changing the label of an annotation layer
    def editLayer(self):
        self.sender_btn = self.sender().text()

        dialog = QDialog(self)
        dialog.setWindowTitle('Change Label')

        layout = QVBoxLayout()
        layout.addWidget(QLabel('Change label of current annotation layer'))
        layout.addWidget(QLabel('Current label: ' + self.sender_btn))

        self.new_label = QLineEdit()
        self.new_label.setPlaceholderText('Enter new label')
        layout.addWidget(self.new_label)

        confirm_button = QPushButton('Confirm')
        confirm_button.pressed.connect(self.renameLayer)
        confirm_button.pressed.connect(dialog.accept)

        layout.addWidget(confirm_button)

        dialog.setLayout(layout)
        dialog.exec()

    # this function eventually changes the label of the annotation layer
    def renameLayer(self):
        widgets = self.anno_bot_widgetLabs.count()
        for i in range(widgets):
            if self.anno_bot_widgetLabs.itemAt(i).widget().text() == self.sender_btn:
                break

        self.anno_bot_widgetLabs.itemAt(i).widget().setText(self.new_label.text())

        # this updates the annotation layers dictionary
        for i in range(len(self.annotation_layers['Dims'])):
            self.annotation_layers['Dims'][i] = self.anno_bot_widgetLabs.itemAt(i).widget().text()

    # this function keeps the dictionary with the item specific annotations updated
    def updateAnnotations(self):
        ## If a rectangle is in selection, edit annotations for that rectangle:
        if len(self.scene.selectedItems()) == 1:
            self.current_key = self.scene.selectedItems()[0]
            for i in range(len(self.item_dict[self.current_key])):
                if self.anno_bot_widgetTxts.itemAt(i).widget().hasFocus():
                    break
            self.item_dict[self.current_key][i] = self.anno_bot_widgetTxts.itemAt(i).widget().text()

        ## If no rectangle is in selection, don't change anything:
        else:
            self.current_key = 'Dims'

    # this function allows the currently selected rectangle to inherit annotations of the previous item (by index)
    # press control + i when a rectangle is selected AND an annotation layer text edit line has focus to trigger this
    def inheritAnnotation(self):
        if self.current_key != 'Dims' and self.item_index[self.current_key] != 1:

            prev_index = self.item_index[self.current_key] - 1
            prev_item = list(self.item_index.keys())[prev_index - 1]

            for i in range(len(self.item_dict[self.current_key])):
                if self.anno_bot_widgetTxts.itemAt(i).widget().hasFocus():
                    prev_annotation = self.item_dict[prev_item][i]
                    self.anno_bot_widgetTxts.itemAt(i).widget().setText(str(prev_annotation))
                    break

    # call this function whenever dictionaries must be cleared
    def clearDictionaries(self):
        self.item_dict = dict()
        self.item_coords = dict()
        self.item_colors = dict()
        self.item_anchors = dict()
        self.item_index = dict()
        self.item_counter = 1

        self.annotation_layers = dict()
        self.annotation_layers['Dims'] = []
        self.dim_counter = 1

        self.current_key = 'Dims'

    # call this function whenever the annotations tabs need to be cleared
    def clearAnnotationTab(self):
        widgets = self.anno_bot_widgetLabs.count()
        for i in range(widgets):
            self.anno_bot_widgetLabs.removeWidget(self.anno_bot_widgetLabs.itemAt(0).widget())
            self.anno_bot_widgetTxts.removeWidget(self.anno_bot_widgetTxts.itemAt(0).widget())

    '''
    ((3.5)) Export functions (annotations to CSV and rendering screenshots)
    '''
    # function to export all annotations within the scene as a csv file
    def exportAnnotations(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Export Annotations as CSV file')

        layout = QHBoxLayout()
        layout.addWidget(QLabel('For CSV export, make your sign:'))
        sign = QLineEdit()
        sign.setPlaceholderText('Your sign here')
        layout.addWidget(sign)
        confirm_button = QPushButton('Confirm')
        confirm_button.pressed.connect(dialog.accept)
        layout.addWidget(confirm_button)

        dialog.setLayout(layout)
        dialog.exec()

        file_name = self.anno_sheetTxt.text()[0:-4]

        # create data frame from dictionary containing all annotations
        df = pd.DataFrame.from_dict(self.item_dict,
                                    orient='index',
                                    columns=self.annotation_layers['Dims'])

        custom_columns = df.columns.tolist()

        # this adds the coordinates and size of the rectangles to the data frame
        df['Index'] = df.index.map(self.item_index)
        df['Coordinates'] = df.index.map(self.item_coords)
        df['Color'] = df.index.map(self.item_colors)
        df['Anchor'] = df.index.map(self.item_anchors)
        df['Source'] = self.anno_sheetTxt.text()

        # the dictionary that maps items to pages must be reversed for addition to the data frame
        item_page = dict()
        for key, value in self.page_items.items():  # credit goes to RLQ
            if type(value) is list:
                for elem in value:
                    item_page[elem] = key
            else:
                item_page[value] = key
        df['Page'] = df.index.map(item_page)

        df = df.sort_values(by=['Index'])

        # reorder columns:
        order = ['Index','Page','Coordinates','Color','Anchor','Source'] + custom_columns
        final_df = df[order]

        if not os.path.exists('Annotated/' + file_name):
            os.makedirs('Annotated/' + file_name)

        final_df.to_csv('Annotated/' + file_name + '/' + file_name + '_' + sign.text() + '.csv',
                        index=False)

    # screenshotting function dialog
    def takeScreenshots(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Make Screenshots')

        layout = QGridLayout()
        layout.addWidget(QLabel('Save Screenshots'), 0, 1)
        current_button = QPushButton('For current page only')
        document_button = QPushButton('For whole document')
        cancel_button = QPushButton('Cancel')

        layout.addWidget(current_button, 1, 0)
        layout.addWidget(document_button, 1, 1)
        layout.addWidget(cancel_button, 1, 2)

        current_button.pressed.connect(dialog.accept)
        current_button.pressed.connect(self.screenshotPage)

        document_button.pressed.connect(dialog.accept)
        document_button.pressed.connect(self.screenshotDocument)

        cancel_button.pressed.connect(dialog.accept)

        dialog.setLayout(layout)
        dialog.exec()

    # make screenshots of items in current page only
    def screenshotPage(self):
        self.scene.clearSelection()

        file_name = self.anno_sheetTxt.text()[0:-4]

        if not os.path.exists('Annotated/' + file_name + '/Screenshots/'):
            os.makedirs('Annotated/' + file_name + '/Screenshots/')

        current_page = self.view_tabs.currentIndex() + 1
        pen = QPen(Qt.GlobalColor.transparent)
        pen.setWidth(1)

        for key in self.item_dict.keys():
            key.setPen(pen)

        for key in self.item_dict.keys():
            if key in self.page_items[current_page]:
                current_index = self.item_index[key]
                x, y = key.x(), key.y()
                width, height = key.rect().width(), key.rect().height()

                rect_source = QRectF(x, y, width, height)
                rect_target = QRectF(0, 0, width, height)

                pixmap = QPixmap(int(width), int(height))

                painter = QPainter(pixmap)

                self.scene.render(painter,
                                  target=rect_target,
                                  source=rect_source)

                painter.end()

                pixmap.save('Annotated/' + file_name + '/Screenshots/' +
                            file_name + '_' + str(current_index) + '.png')

        pen.setColor(Qt.GlobalColor.red)
        for key in self.item_dict.keys():
            key.setPen(pen)

    # make screenshots of all items (page by page)
    def screenshotDocument(self):
        self.scene.clearSelection()

        file_name = self.anno_sheetTxt.text()[0:-4]

        if not os.path.exists('Annotated/' + file_name + '/Screenshots/'):
            os.makedirs('Annotated/' + file_name + '/Screenshots/')

        # make rectangles invisible
        pen = QPen(Qt.GlobalColor.transparent)
        pen.setWidth(1)
        for key in self.item_dict.keys():
            key.setPen(pen)

        # go through all pages starting with the first
        for page, val in self.page_index.items():
            self.view_tabs.setCurrentIndex(val)

            for item in self.scene.items():
                if item.zValue() == 1:
                    self.scene.removeItem(item)
                else:
                    item.setZValue(0)
                    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
                    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

            self.scene.addPixmap(QPixmap('temp/' + page))
            self.scene.items()[0].setZValue(1)

            for item in self.page_items[val]:
                item.setZValue(2)
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

            # make screenshots of items in current page
            for key in self.item_dict.keys():
                if key in self.page_items[val]:
                    current_index = self.item_index[key]
                    x, y = key.x(), key.y()
                    width, height = key.rect().width(), key.rect().height()

                    rect_source = QRectF(x, y, width, height)
                    rect_target = QRectF(0, 0, width, height)

                    pixmap = QPixmap(int(width), int(height))

                    painter = QPainter(pixmap)
                    self.scene.render(painter,
                                      target=rect_target,
                                      source=rect_source)
                    painter.end()

                    pixmap.save('Annotated/' + file_name + '/Screenshots/' +
                                file_name + '_' + str(current_index) + '.png')

        # make rectangles visible again
        pen.setColor(Qt.GlobalColor.red)
        for key in self.item_dict.keys():
            key.setPen(pen)

    '''
    ((3.6)) MISC
    '''
    def contextMenuEvent(self, event):
        self.context_menu.exec(event.globalPos())

    # this function tracks the cursor position
    def mouseTracker(self, pos):
        current_index = self.view_tabs.currentIndex()
        self.last_pos = self.view_tabs.widget(current_index).mapToGlobal(pos)
        self.scene_pos = self.view_tabs.widget(current_index).mapToScene(pos)

        # the code below updates item coordinates if an item is selected
        item = self.scene.selectedItems()
        if len(item) > 0:
            self.item_coords[item[0]] = [round(item[0].x(), 2),
                                         round(item[0].y(), 2),
                                         item[0].rect().width(),
                                         item[0].rect().height()]
            self.anno_coordTxt.setText(str(self.item_coords[self.current_key]))

    # Various key bound actions
    def keyPressEvent(self, event):
        # This KeyPressEvent enables setting new annotation layers directly from the input line by pressing Return
        if self.anno_new_layer_title.hasFocus():
            if event.key() == Qt.Key.Key_Return:
                self.addAnnotationLayer()
                self.anno_new_layer_title.setText('')

        # Below are KeyPressEvents that modify a selected rectangle
        item = self.scene.selectedItems()
        if len(item) == 1:

            # Control modifier allows for 1 pixel size adjustments to selected rectangle:
            if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                if event.key() == Qt.Key.Key_Left or event.key() == Qt.Key.Key_A:
                    item[0].setRect(0, 0, int(item[0].rect().width()) - 1, int(item[0].rect().height()))
                    # update coordinates dictionary
                    self.item_coords[item[0]] = [round(item[0].x(), 2),
                                                 round(item[0].y(), 2),
                                                 item[0].rect().width(),
                                                 item[0].rect().height()]
                    self.anno_coordTxt.setText(str(self.item_coords[self.current_key]))

                elif event.key() == Qt.Key.Key_Right or event.key() == Qt.Key.Key_D:
                    item[0].setRect(0, 0, int(item[0].rect().width()) + 1, int(item[0].rect().height()))
                    # update coordinates dictionary
                    self.item_coords[item[0]] = [round(item[0].x(), 2),
                                                 round(item[0].y(), 2),
                                                 item[0].rect().width(),
                                                 item[0].rect().height()]
                    self.anno_coordTxt.setText(str(self.item_coords[self.current_key]))

                elif event.key() == Qt.Key.Key_Up or event.key() == Qt.Key.Key_W:
                    item[0].setRect(0, 0, int(item[0].rect().width()), int(item[0].rect().height()) - 1)
                    # update coordinates dictionary
                    self.item_coords[item[0]] = [round(item[0].x(), 2),
                                                 round(item[0].y(), 2),
                                                 item[0].rect().width(),
                                                 item[0].rect().height()]
                    self.anno_coordTxt.setText(str(self.item_coords[self.current_key]))

                elif event.key() == Qt.Key.Key_Down or event.key() == Qt.Key.Key_S:
                    item[0].setRect(0, 0, int(item[0].rect().width()), int(item[0].rect().height()) + 1)
                    # update coordinates dictionary
                    self.item_coords[item[0]] = [round(item[0].x(), 2),
                                                 round(item[0].y(), 2),
                                                 item[0].rect().width(),
                                                 item[0].rect().height()]
                    self.anno_coordTxt.setText(str(self.item_coords[self.current_key]))

                elif event.key() == Qt.Key.Key_Return:
                    # switch to next item; if at last index, switch to item with index 1
                    current_index = self.item_index[self.current_key]
                    current_page = self.view_tabs.currentIndex()

                    if current_index + 1 not in self.item_index.values():
                        current_index = 0

                    next_item = [key for key, val in self.item_index.items() if val == current_index + 1]
                    self.scene.clearSelection()
                    next_item[0].setSelected(True)
                    self.view_tabs.widget(current_page).centerOn(next_item[0].pos())

                    # the lines below make it so that after switching items, the first annotation layer is selected
                    if self.anno_bot_widgetTxts.count() > 0:
                        self.anno_bot_widgetTxts.itemAt(0).widget().setFocus()
                        self.anno_bot_widgetTxts.itemAt(0).widget().selectAll()

                elif event.key() == Qt.Key.Key_I:
                    # inherit current annotation of previous item (by index)
                    self.inheritAnnotation()

                elif event.key() == Qt.Key.Key_Space:
                    # press Space to set anchor
                    self.setAnchor()

            # Shift modifier allows for 5 pixel size adjustments to selected rectangle:
            elif event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                if event.key() == Qt.Key.Key_Left or event.key() == Qt.Key.Key_A:
                    item[0].setRect(0, 0, int(item[0].rect().width()) - 5, int(item[0].rect().height()))
                    # update coordinates dictionary
                    self.item_coords[item[0]] = [round(item[0].x(), 2),
                                                 round(item[0].y(), 2),
                                                 item[0].rect().width(),
                                                 item[0].rect().height()]
                    self.anno_coordTxt.setText(str(self.item_coords[self.current_key]))

                elif event.key() == Qt.Key.Key_Right or event.key() == Qt.Key.Key_D:
                    item[0].setRect(0, 0, int(item[0].rect().width()) + 5, int(item[0].rect().height()))
                    # update coordinates dictionary
                    self.item_coords[item[0]] = [round(item[0].x(), 2),
                                                 round(item[0].y(), 2),
                                                 item[0].rect().width(),
                                                 item[0].rect().height()]
                    self.anno_coordTxt.setText(str(self.item_coords[self.current_key]))

                elif event.key() == Qt.Key.Key_Up or event.key() == Qt.Key.Key_W:
                    item[0].setRect(0, 0, int(item[0].rect().width()), int(item[0].rect().height()) - 5)
                    # update coordinates dictionary
                    self.item_coords[item[0]] = [round(item[0].x(), 2),
                                                 round(item[0].y(), 2),
                                                 item[0].rect().width(),
                                                 item[0].rect().height()]
                    self.anno_coordTxt.setText(str(self.item_coords[self.current_key]))

                elif event.key() == Qt.Key.Key_Down or event.key() == Qt.Key.Key_S:
                    item[0].setRect(0, 0, int(item[0].rect().width()), int(item[0].rect().height()) + 5)
                    # update coordinates dictionary
                    self.item_coords[item[0]] = [round(item[0].x(), 2),
                                                 round(item[0].y(), 2),
                                                 item[0].rect().width(),
                                                 item[0].rect().height()]
                    self.anno_coordTxt.setText(str(self.item_coords[self.current_key]))

                elif event.key() == Qt.Key.Key_Space:
                    # press Space to set anchor
                    self.setAnchor()

            # Without any modifier, the position of the rectangle can be adjusted in 1 pixel increments
            else:
                if event.key() == Qt.Key.Key_Left or event.key() == Qt.Key.Key_A:
                    item[0].setPos(item[0].x() - 1, item[0].y())
                    # update coordinates dictionary
                    self.item_coords[item[0]] = [round(item[0].x(), 2),
                                                 round(item[0].y(), 2),
                                                 item[0].rect().width(),
                                                 item[0].rect().height()]
                    self.anno_coordTxt.setText(str(self.item_coords[self.current_key]))

                elif event.key() == Qt.Key.Key_Right or event.key() == Qt.Key.Key_D:
                    item[0].setPos(item[0].x() + 1, item[0].y())
                    # update coordinates dictionary
                    self.item_coords[item[0]] = [round(item[0].x(), 2),
                                                 round(item[0].y(), 2),
                                                 item[0].rect().width(),
                                                 item[0].rect().height()]
                    self.anno_coordTxt.setText(str(self.item_coords[self.current_key]))

                elif event.key() == Qt.Key.Key_Up or event.key() == Qt.Key.Key_W:
                    item[0].setPos(item[0].x(), item[0].y() - 1)
                    # update coordinates dictionary
                    self.item_coords[item[0]] = [round(item[0].x(), 2),
                                                 round(item[0].y(), 2),
                                                 item[0].rect().width(),
                                                 item[0].rect().height()]
                    self.anno_coordTxt.setText(str(self.item_coords[self.current_key]))

                elif event.key() == Qt.Key.Key_Down or event.key() == Qt.Key.Key_S:
                    item[0].setPos(item[0].x(), item[0].y() + 1)
                    # update coordinates dictionary
                    self.item_coords[item[0]] = [round(item[0].x(), 2),
                                                 round(item[0].y(), 2),
                                                 item[0].rect().width(),
                                                 item[0].rect().height()]
                    self.anno_coordTxt.setText(str(self.item_coords[self.current_key]))

                elif event.key() == Qt.Key.Key_Space:
                    # press Space to set anchor
                    self.setAnchor()

        # pressing/releasing Alt (without any modifier) has to purposes:
        # (1) it toggles all items movable on pressing alt / immovable on releasing alt
        # (2) if an item is selected, it places another rectangle on top, which can be dragged around to adjust the size
        # of the selected item; this adjustment happens on release of Alt
        if event.key() == Qt.Key.Key_Alt:
            item = self.scene.selectedItems()
            if len(item) == 1:
                for key in self.item_index.keys():
                    key.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

                self.sizer = QGraphicsRectItem(0, 0, item[0].rect().width(), item[0].rect().height())

                self.sizer.setPos(item[0].x(), item[0].y())

                self.sizer.setPen(self.rect_pen)
                self.sizer.setZValue(2)
                self.sizer.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

                self.scene.addItem(self.sizer)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Alt and not self.view.is_pressed:

            for key in self.item_index.keys():
                key.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

            self.toggleItems()

            # this is the keyRelease-part to the item resizing function;
            # only on release is the actual resizing triggered
            item = self.scene.selectedItems()
            if len(item) == 1:
                x = self.sizer.x()
                y = self.sizer.y()

                self.scene.removeItem(self.sizer)
                self.resizeItem(x, y)

                try: self.scene.removeItem(self.sizer)
                except: return

        elif event.key() == Qt.Key.Key_Alt:
            # the part below is there in order to prevent a glitch that only happens when Alt is released before the
            # mouse; in this case, now all items are set immovable until toggled movable again
            self.toggle_action.setChecked(True)
            self.toggleItems()

            # this is the keyRelease-part to the item resizing function;
            # only on release is the actual resizing triggered
            item = self.scene.selectedItems()
            if len(item) == 1:
                x = self.sizer.x()
                y = self.sizer.y()

                self.scene.removeItem(self.sizer)
                self.resizeItem(x, y)

                try: self.scene.removeItem(self.sizer)
                except: return


app = QApplication(sys.argv)
app.setStyle('Fusion')
window = MainWindow()
window.show()
app.exec()