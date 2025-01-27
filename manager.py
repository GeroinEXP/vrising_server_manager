import sys
import json
import ftplib
from datetime import datetime
from io import BytesIO
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QTableWidget,
                             QTableWidgetItem, QDialog, QFormLayout, QSpinBox, QCheckBox, QMessageBox,
                             QSplitter, QHeaderView)
from PyQt5.QtCore import Qt, QSettings

class FTPConnectionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.settings = QSettings("V Rising", "Server Manager")
        self.initUI()
        self.load_settings()

    def initUI(self):
        layout = QVBoxLayout()

        self.host_input = QLineEdit()
        self.port_input = QLineEdit('21')
        self.user_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)

        self.connect_btn = QPushButton('Подключиться')
        self.connect_btn.clicked.connect(self.connect_ftp)

        self.save_btn = QPushButton('Сохранить настройки')
        self.save_btn.clicked.connect(self.save_settings)

        form_layout = QFormLayout()
        form_layout.addRow('Хост:', self.host_input)
        form_layout.addRow('Порт:', self.port_input)
        form_layout.addRow('Пользователь:', self.user_input)
        form_layout.addRow('Пароль:', self.password_input)
        
        layout.addLayout(form_layout)
        layout.addWidget(self.connect_btn)
        layout.addWidget(self.save_btn)
        self.setLayout(layout)

    def connect_ftp(self):
        try:
            self.parent.ftp = ftplib.FTP()
            self.parent.ftp.connect(
                self.host_input.text(),
                int(self.port_input.text())
            )
            self.parent.ftp.login(
                self.user_input.text(),
                self.password_input.text()
            )
            self.parent.ftp.set_pasv(True)
            QMessageBox.information(self, 'Успех', 'Успешное подключение к FTP!')
            self.parent.load_configs()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка подключения: {str(e)}')

    def save_settings(self):
        self.settings.setValue('host', self.host_input.text())
        self.settings.setValue('port', self.port_input.text())
        self.settings.setValue('user', self.user_input.text())
        self.settings.setValue('password', self.password_input.text())
        QMessageBox.information(self, 'Сохранено', 'Настройки подключения сохранены!')

    def load_settings(self):
        self.host_input.setText(self.settings.value('host', ''))
        self.port_input.setText(self.settings.value('port', '21'))
        self.user_input.setText(self.settings.value('user', ''))
        self.password_input.setText(self.settings.value('password', ''))

class ConfigEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Параметр', 'Значение'])
        layout = QVBoxLayout()
        layout.addWidget(self.tree)
        self.setLayout(layout)

    def load_config(self, config_text):
        self.tree.clear()
        current_section = None
        for line in config_text.split('\n'):
            line = line.strip()
            if line.startswith('[') and line.endswith(']'):
                current_section = QTreeWidgetItem(self.tree, [line[1:-1], ''])
                current_section.setExpanded(True)
            elif '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.split('#')[0].strip()
                
                item = QTreeWidgetItem(current_section)
                item.setText(0, key)
                
                if value.lower() in ('true', 'false'):
                    checkbox = QCheckBox()
                    checkbox.setChecked(value.lower() == 'true')
                    checkbox.stateChanged.connect(lambda state, i=item: self.update_config_value(i, state))
                    self.tree.setItemWidget(item, 1, checkbox)
                else:
                    try:
                        int_value = int(value)
                        spinbox = QSpinBox()
                        spinbox.setMaximum(999999)
                        spinbox.setValue(int_value)
                        spinbox.valueChanged.connect(lambda val, i=item: self.update_config_value(i, val))
                        self.tree.setItemWidget(item, 1, spinbox)
                    except ValueError:
                        line_edit = QLineEdit(value)
                        line_edit.textChanged.connect(lambda text, i=item: self.update_config_value(i, text))
                        self.tree.setItemWidget(item, 1, line_edit)

    def update_config_value(self, item, value):
        item.setData(1, Qt.UserRole, value)

    def get_config(self):
        config = []
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            section = root.child(i)
            config.append(f'[{section.text(0)}]')
            for j in range(section.childCount()):
                item = section.child(j)
                value = item.data(1, Qt.UserRole)
                config.append(f'{item.text(0)} = {value}')
        return '\n'.join(config)

class ProductsEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        self.table = QTableWidget()
        self.table.setColumnCount(7)  # Добавили столбец для isBuff
        self.table.setHorizontalHeaderLabels(['ID', 'Name', 'Price', 'Stock', 'Stack', 'Currency', 'isBuff'])
        
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton('Добавить')
        self.add_btn.clicked.connect(self.add_product)
        self.remove_btn = QPushButton('Удалить')
        self.remove_btn.clicked.connect(self.remove_product)
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        
        layout.addWidget(self.table)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def load_products(self, products):
        self.table.setRowCount(len(products))
        for row, product in enumerate(products):
            self.table.setItem(row, 0, QTableWidgetItem(str(product['id'])))
            self.table.setItem(row, 1, QTableWidgetItem(product['name']))
            self.table.setItem(row, 2, QTableWidgetItem(str(product['price'])))
            self.table.setItem(row, 3, QTableWidgetItem(str(product['stock'])))
            self.table.setItem(row, 4, QTableWidgetItem(str(product['stack'])))
            self.table.setItem(row, 5, QTableWidgetItem(str(product['currency'])))
            
            # Добавляем чекбокс для isBuff
            checkbox = QCheckBox()
            checkbox.setChecked(product['isBuff'])
            self.table.setCellWidget(row, 6, checkbox)

    def add_product(self):
        dialog = ProductDialog(self)
        if dialog.exec_():
            product = dialog.get_product()
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(product['id'])))
            self.table.setItem(row, 1, QTableWidgetItem(product['name']))
            self.table.setItem(row, 2, QTableWidgetItem(str(product['price'])))
            self.table.setItem(row, 3, QTableWidgetItem(str(product['stock'])))
            self.table.setItem(row, 4, QTableWidgetItem(str(product['stack'])))
            self.table.setItem(row, 5, QTableWidgetItem(str(product['currency'])))
            
            # Добавляем чекбокс для isBuff
            checkbox = QCheckBox()
            checkbox.setChecked(product['isBuff'])
            self.table.setCellWidget(row, 6, checkbox)

    def remove_product(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)

    def get_products(self):
        products = []
        for row in range(self.table.rowCount()):
            product = {
                'id': int(self.table.item(row, 0).text()),
                'name': self.table.item(row, 1).text(),
                'price': int(self.table.item(row, 2).text()),
                'stock': int(self.table.item(row, 3).text()),
                'stack': int(self.table.item(row, 4).text()),
                'currency': int(self.table.item(row, 5).text()),
                'isBuff': self.table.cellWidget(row, 6).isChecked()  # Получаем значение isBuff
            }
            products.append(product)
        return products

class ProductDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Добавить товар')
        layout = QFormLayout()
        
        self.id_input = QSpinBox()
        self.id_input.setRange(-999999999, 999999999)
        self.name_input = QLineEdit()
        self.price_input = QSpinBox()
        self.price_input.setRange(0, 999999)
        self.stock_input = QSpinBox()
        self.stock_input.setRange(0, 999999)
        self.stack_input = QSpinBox()
        self.stack_input.setRange(0, 999999)
        self.currency_input = QSpinBox()
        self.currency_input.setRange(0, 999999999)
        self.is_buff_checkbox = QCheckBox('isBuff')  # Добавляем чекбокс для isBuff
        
        layout.addRow('ID:', self.id_input)
        layout.addRow('Название:', self.name_input)
        layout.addRow('Цена:', self.price_input)
        layout.addRow('Stock:', self.stock_input)
        layout.addRow('Stack:', self.stack_input)
        layout.addRow('Currency:', self.currency_input)
        layout.addRow(self.is_buff_checkbox)  # Добавляем чекбокс в форму
        
        buttons = QHBoxLayout()
        ok_btn = QPushButton('OK')
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        
        layout.addRow(buttons)
        self.setLayout(layout)

    def get_product(self):
        return {
            'id': self.id_input.value(),
            'name': self.name_input.text(),
            'price': self.price_input.value(),
            'stock': self.stock_input.value(),
            'stack': self.stack_input.value(),
            'currency': self.currency_input.value(),
            'isBuff': self.is_buff_checkbox.isChecked()  # Добавляем isBuff
        }

class CurrencyTracker(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        splitter = QSplitter(Qt.Vertical)

        self.online_table = QTableWidget()
        self.online_table.setColumnCount(3)
        self.online_table.setHorizontalHeaderLabels(['Игрок', 'Последний день', 'Время подключения'])
        self.online_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.currency_table = QTableWidget()
        self.currency_table.setColumnCount(5)
        self.currency_table.setHorizontalHeaderLabels(['Игрок', 'Дата', 'NPC', 'VBlood', 'PvP'])
        self.currency_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.figure = plt.figure()
        self.canvas = FigureCanvas(self.figure)
        
        splitter.addWidget(self.online_table)
        splitter.addWidget(self.currency_table)
        splitter.addWidget(self.canvas)
        
        layout.addWidget(splitter)
        self.setLayout(layout)

    def load_data(self, online_data, currency_data):
        self.online_table.setRowCount(len(online_data))
        for row, entry in enumerate(online_data):
            self.online_table.setItem(row, 0, QTableWidgetItem(entry['player']))
            self.online_table.setItem(row, 1, QTableWidgetItem(entry['LastDayConnection']))
            self.online_table.setItem(row, 2, QTableWidgetItem(entry['LastDateTime']))

        self.currency_table.setRowCount(len(currency_data))
        for row, entry in enumerate(currency_data):
            self.currency_table.setItem(row, 0, QTableWidgetItem(entry['CharacterName']))
            self.currency_table.setItem(row, 1, QTableWidgetItem(entry['date']))
            self.currency_table.setItem(row, 2, QTableWidgetItem(str(entry['AmountNpc'])))
            self.currency_table.setItem(row, 3, QTableWidgetItem(str(entry['AmountVBlood'])))
            self.currency_table.setItem(row, 4, QTableWidgetItem(str(entry['AmountPvp'])))

        self.update_chart(currency_data)

    def update_chart(self, data):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        players = [entry['CharacterName'] for entry in data]
        npc = [entry['AmountNpc'] for entry in data]
        vblood = [entry['AmountVBlood'] for entry in data]
        pvp = [entry['AmountPvp'] for entry in data]

        bar_width = 0.25
        index = range(len(players))

        ax.bar(index, npc, bar_width, label='NPC')
        ax.bar([i + bar_width for i in index], vblood, bar_width, label='VBlood')
        ax.bar([i + 2*bar_width for i in index], pvp, bar_width, label='PvP')

        ax.set_xlabel('Игроки')
        ax.set_ylabel('Количество валюты')
        ax.set_title('Распределение валюты по игрокам')
        ax.set_xticks([i + bar_width for i in index])
        ax.set_xticklabels(players, rotation=45)
        ax.legend()

        self.canvas.draw()

class AnnouncementEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        
        # Создаем таблицу для анонсов
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['Название', 'Время', 'Сообщение', 'Одноразовый'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Кнопки управления
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton('Добавить')
        self.add_btn.clicked.connect(self.add_announcement)
        self.remove_btn = QPushButton('Удалить')
        self.remove_btn.clicked.connect(self.remove_announcement)
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        
        layout.addWidget(self.table)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def load_announcements(self, announcements):
        self.table.setRowCount(len(announcements))
        for row, announcement in enumerate(announcements):
            self.table.setItem(row, 0, QTableWidgetItem(announcement['Name']))
            self.table.setItem(row, 1, QTableWidgetItem(announcement['Time']))
            self.table.setItem(row, 2, QTableWidgetItem(announcement['Message']))
            
            checkbox = QCheckBox()
            checkbox.setChecked(announcement['OneTime'])
            self.table.setCellWidget(row, 3, checkbox)

    def add_announcement(self):
        dialog = AnnouncementDialog(self)
        if dialog.exec_():
            announcement = dialog.get_announcement()
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(announcement['Name']))
            self.table.setItem(row, 1, QTableWidgetItem(announcement['Time']))
            self.table.setItem(row, 2, QTableWidgetItem(announcement['Message']))
            
            checkbox = QCheckBox()
            checkbox.setChecked(announcement['OneTime'])
            self.table.setCellWidget(row, 3, checkbox)

    def remove_announcement(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)

    def get_announcements(self):
        announcements = []
        for row in range(self.table.rowCount()):
            announcement = {
                'Name': self.table.item(row, 0).text(),
                'Time': self.table.item(row, 1).text(),
                'Message': self.table.item(row, 2).text(),
                'OneTime': self.table.cellWidget(row, 3).isChecked()
            }
            announcements.append(announcement)
        return announcements

class AnnouncementDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Добавить анонс')
        layout = QFormLayout()
        
        self.name_input = QLineEdit()
        self.time_input = QLineEdit()
        self.message_input = QLineEdit()
        self.one_time_checkbox = QCheckBox('Одноразовый анонс')
        
        layout.addRow('Название:', self.name_input)
        layout.addRow('Время (HH:MMam/pm):', self.time_input)
        layout.addRow('Сообщение:', self.message_input)
        layout.addRow(self.one_time_checkbox)
        
        buttons = QHBoxLayout()
        ok_btn = QPushButton('OK')
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton('Отмена')
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        
        layout.addRow(buttons)
        self.setLayout(layout)

    def get_announcement(self):
        return {
            'Name': self.name_input.text(),
            'Time': self.time_input.text(),
            'Message': self.message_input.text(),
            'OneTime': self.one_time_checkbox.isChecked()
        }

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ftp = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('V Rising Server Manager')
        self.setGeometry(100, 100, 1000, 800)

        self.tabs = QTabWidget()
        
        self.ftp_connection = FTPConnectionWidget(self)
        self.config_editor = ConfigEditor()
        self.products_editor = ProductsEditor()
        self.currency_tracker = CurrencyTracker()
        self.announcement_editor = AnnouncementEditor()
        
        self.tabs.addTab(self.ftp_connection, 'FTP подключение')
        self.tabs.addTab(self.config_editor, 'Настройки')
        self.tabs.addTab(self.products_editor, 'Магазин')
        self.tabs.addTab(self.currency_tracker, 'Статистика')
        self.tabs.addTab(self.announcement_editor, 'Анонсы')
        
        self.save_btn = QPushButton('Сохранить все изменения', self)
        self.save_btn.clicked.connect(self.save_all)
        
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        main_layout.addWidget(self.save_btn)
        
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def load_configs(self):
        try:
            config_path = '/BepInEx/config/BloodyRewards.cfg'
            products_path = '/BepInEx/config/BloodyShop/products_list.json'
            online_path = '/BepInEx/config/BloodyRewards/dayli_time_online_list.json'
            currency_path = '/BepInEx/config/BloodyRewards/user_currencies_per_day.json'
            announcements_path = '/BepInEx/config/KindredCommands/announcements.json'

            # Загрузка BloodyRewards.cfg
            with BytesIO() as f:
                self.ftp.retrbinary(f'RETR {config_path}', f.write)
                self.config_editor.load_config(f.getvalue().decode('utf-8'))
            
            # Загрузка products_list.json
            with BytesIO() as f:
                self.ftp.retrbinary(f'RETR {products_path}', f.write)
                products = json.loads(f.getvalue().decode('utf-8'))
                self.products_editor.load_products(products)

            # Загрузка статистики
            with BytesIO() as f:
                self.ftp.retrbinary(f'RETR {online_path}', f.write)
                online_data = json.loads(f.getvalue().decode('utf-8'))

            with BytesIO() as f:
                self.ftp.retrbinary(f'RETR {currency_path}', f.write)
                currency_data = json.loads(f.getvalue().decode('utf-8'))

            with BytesIO() as f:
                self.ftp.retrbinary(f'RETR {announcements_path}', f.write)
                announcements = json.loads(f.getvalue().decode('utf-8'))
                self.announcement_editor.load_announcements(announcements)

            self.currency_tracker.load_data(online_data, currency_data)
            
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка загрузки файлов: {str(e)}')

    def save_all(self):
        try:
            config_path = '/BepInEx/config/BloodyRewards.cfg'
            products_path = '/BepInEx/config/BloodyShop/products_list.json'
            announcements_path = '/BepInEx/config/KindredCommands/announcements.json'

            # Сохранение BloodyRewards.cfg
            config_data = self.config_editor.get_config().encode('utf-8')
            with BytesIO(config_data) as f:
                self.ftp.storbinary(f'STOR {config_path}', f)
            
            # Сохранение products_list.json
            products_data = json.dumps(self.products_editor.get_products(), indent=2).encode('utf-8')
            with BytesIO(products_data) as f:
                self.ftp.storbinary(f'STOR {products_path}', f)
            
            # Сохранение announcements.json
            announcements_data = json.dumps(self.announcement_editor.get_announcements(), indent=2).encode('utf-8')
            with BytesIO(announcements_data) as f:
                self.ftp.storbinary(f'STOR {announcements_path}', f)
            
            QMessageBox.information(self, 'Успех', 'Все изменения сохранены!')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка сохранения: {str(e)}')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
