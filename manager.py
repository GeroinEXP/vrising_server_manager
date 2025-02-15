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
                             QSplitter, QHeaderView, QComboBox, QInputDialog, QDoubleSpinBox)
from PyQt5.QtCore import Qt, QSettings
import numpy as np
import pandas as pd

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
        # Преобразуем значение в строку в зависимости от типа виджета
        if isinstance(self.tree.itemWidget(item, 1), QCheckBox):
            str_value = str(value == Qt.Checked).lower()
        elif isinstance(self.tree.itemWidget(item, 1), QSpinBox):
            str_value = str(value)
        else:
            str_value = str(value)
        
        item.setData(1, Qt.UserRole, str_value)

    def get_config(self):
        config = []
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            section = root.child(i)
            config.append(f'[{section.text(0)}]')
            for j in range(section.childCount()):
                item = section.child(j)
                value = item.data(1, Qt.UserRole)
                
                # Проверка на None и установка значения по умолчанию
                if value is None:
                    widget = self.tree.itemWidget(item, 1)
                    if isinstance(widget, QCheckBox):
                        value = str(widget.isChecked()).lower()
                    elif isinstance(widget, QSpinBox):
                        value = str(widget.value())
                    elif isinstance(widget, QLineEdit):
                        value = widget.text()
                    item.setData(1, Qt.UserRole, value)
                
                config.append(f'{item.text(0)} = {value}')
        return '\n'.join(config)

class ProductsEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.merchants = []
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        
        # Список торговцев
        merchant_layout = QHBoxLayout()
        self.merchant_list = QComboBox()
        self.merchant_list.currentIndexChanged.connect(self.load_merchant_items)
        
        self.add_merchant_btn = QPushButton('Добавить торговца')
        self.add_merchant_btn.clicked.connect(self.add_merchant)
        self.remove_merchant_btn = QPushButton('Удалить торговца')
        self.remove_merchant_btn.clicked.connect(self.remove_merchant)
        
        merchant_layout.addWidget(QLabel('Торговец:'))
        merchant_layout.addWidget(self.merchant_list)
        merchant_layout.addWidget(self.add_merchant_btn)
        merchant_layout.addWidget(self.remove_merchant_btn)
        
        # Настройки торговца
        merchant_config_layout = QFormLayout()
        self.merchant_name = QLineEdit()
        self.merchant_prefab = QSpinBox()
        self.merchant_prefab.setRange(-2147483648, 2147483647)
        self.merchant_x = QDoubleSpinBox()
        self.merchant_x.setRange(-10000, 10000)
        self.merchant_x.setDecimals(4)
        self.merchant_z = QDoubleSpinBox()
        self.merchant_z.setRange(-10000, 10000)
        self.merchant_z.setDecimals(4)
        self.merchant_enabled = QCheckBox('Включен')
        self.merchant_immortal = QCheckBox('Бессмертный')
        self.merchant_can_move = QCheckBox('Может двигаться')
        self.merchant_autorepawn = QCheckBox('Авто-респаун')
        
        merchant_config_layout.addRow('Имя:', self.merchant_name)
        merchant_config_layout.addRow('PrefabGUID:', self.merchant_prefab)
        merchant_config_layout.addRow('X:', self.merchant_x)
        merchant_config_layout.addRow('Z:', self.merchant_z)
        merchant_config_layout.addRow(self.merchant_enabled)
        merchant_config_layout.addRow(self.merchant_immortal)
        merchant_config_layout.addRow(self.merchant_can_move)
        merchant_config_layout.addRow(self.merchant_autorepawn)
        
        # Таблица товаров
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            'Товар (ID)', 'Кол-во товара', 
            'Валюта (ID)', 'Цена', 
            'Запас', 'Авто-пополнение'
        ])
        
        # Кнопки управления товарами
        btn_layout = QHBoxLayout()
        self.add_item_btn = QPushButton('Добавить товар')
        self.add_item_btn.clicked.connect(self.add_item)
        self.remove_item_btn = QPushButton('Удалить товар')
        self.remove_item_btn.clicked.connect(self.remove_item)
        
        btn_layout.addWidget(self.add_item_btn)
        btn_layout.addWidget(self.remove_item_btn)
        
        layout.addLayout(merchant_layout)
        layout.addLayout(merchant_config_layout)
        layout.addWidget(self.table)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def load_merchants(self, merchants_data):
        self.merchants = merchants_data
        self.merchant_list.clear()
        for merchant in merchants_data:
            self.merchant_list.addItem(merchant['name'])
        if merchants_data:
            self.load_merchant_items(0)

    def load_merchant_items(self, index):
        if index < 0 or not self.merchants:
            return
            
        merchant = self.merchants[index]
        
        # Загружаем настройки торговца
        self.merchant_name.setText(merchant['name'])
        self.merchant_prefab.setValue(merchant['PrefabGUID'])
        self.merchant_x.setValue(merchant['config']['x'])
        self.merchant_z.setValue(merchant['config']['z'])
        self.merchant_enabled.setChecked(merchant['config']['IsEnabled'])
        self.merchant_immortal.setChecked(merchant['config']['Immortal'])
        self.merchant_can_move.setChecked(merchant['config']['CanMove'])
        self.merchant_autorepawn.setChecked(merchant['config']['Autorepawn'])
        
        # Загружаем товары
        self.table.setRowCount(len(merchant['items']))
        for row, item in enumerate(merchant['items']):
            self.table.setItem(row, 0, QTableWidgetItem(str(item['OutputItem'])))
            self.table.setItem(row, 1, QTableWidgetItem(str(item['OutputAmount'])))
            self.table.setItem(row, 2, QTableWidgetItem(str(item['InputItem'])))
            self.table.setItem(row, 3, QTableWidgetItem(str(item['InputAmount'])))
            self.table.setItem(row, 4, QTableWidgetItem(str(item['StockAmount'])))
            
            checkbox = QCheckBox()
            checkbox.setChecked(item['Autorefill'])
            self.table.setCellWidget(row, 5, checkbox)

    def add_merchant(self):
        name, ok = QInputDialog.getText(self, 'Новый торговец', 'Имя торговца:')
        if ok and name:
            new_merchant = {
                "name": name,
                "PrefabGUID": -208499374,
                "items": [],
                "merchantEntity": {},
                "config": {
                    "IsEnabled": True,
                    "x": 0.0,
                    "z": 0.0,
                    "Immortal": True,
                    "CanMove": False,
                    "Autorepawn": True
                }
            }
            self.merchants.append(new_merchant)
            self.merchant_list.addItem(name)
            self.merchant_list.setCurrentIndex(len(self.merchants) - 1)

    def remove_merchant(self):
        current_index = self.merchant_list.currentIndex()
        if current_index >= 0:
            self.merchants.pop(current_index)
            self.merchant_list.removeItem(current_index)
            if self.merchants:
                self.load_merchant_items(0)
            else:
                self.table.setRowCount(0)

    def add_item(self):
        dialog = MerchantItemDialog(self)
        if dialog.exec_():
            item = dialog.get_item()
            current_index = self.merchant_list.currentIndex()
            if current_index >= 0:
                self.merchants[current_index]['items'].append(item)
                self.load_merchant_items(current_index)

    def remove_item(self):
        current_row = self.table.currentRow()
        current_merchant = self.merchant_list.currentIndex()
        if current_row >= 0 and current_merchant >= 0:
            self.merchants[current_merchant]['items'].pop(current_row)
            self.load_merchant_items(current_merchant)

    def get_merchants(self):
        # Сохраняем текущие изменения перед возвратом
        current_index = self.merchant_list.currentIndex()
        if current_index >= 0:
            merchant = self.merchants[current_index]
            merchant['name'] = self.merchant_name.text()
            merchant['PrefabGUID'] = self.merchant_prefab.value()
            merchant['config']['x'] = self.merchant_x.value()
            merchant['config']['z'] = self.merchant_z.value()
            merchant['config']['IsEnabled'] = self.merchant_enabled.isChecked()
            merchant['config']['Immortal'] = self.merchant_immortal.isChecked()
            merchant['config']['CanMove'] = self.merchant_can_move.isChecked()
            merchant['config']['Autorepawn'] = self.merchant_autorepawn.isChecked()
            
            merchant['items'] = []
            for row in range(self.table.rowCount()):
                item = {
                    'OutputItem': int(self.table.item(row, 0).text()),
                    'OutputAmount': int(self.table.item(row, 1).text()),
                    'InputItem': int(self.table.item(row, 2).text()),
                    'InputAmount': int(self.table.item(row, 3).text()),
                    'StockAmount': int(self.table.item(row, 4).text()),
                    'Autorefill': self.table.cellWidget(row, 5).isChecked()
                }
                merchant['items'].append(item)
        
        return self.merchants

class MerchantItemDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Добавить товар')
        layout = QFormLayout()
        
        self.output_item = QSpinBox()
        self.output_item.setRange(-2147483648, 2147483647)
        self.output_amount = QSpinBox()
        self.output_amount.setRange(1, 999999)
        self.input_item = QSpinBox()
        self.input_item.setRange(-2147483648, 2147483647)
        self.input_amount = QSpinBox()
        self.input_amount.setRange(1, 999999)
        self.stock_amount = QSpinBox()
        self.stock_amount.setRange(0, 999999)
        self.autorefill = QCheckBox('Авто-пополнение')
        self.autorefill.setChecked(True)
        
        layout.addRow('ID товара:', self.output_item)
        layout.addRow('Количество товара:', self.output_amount)
        layout.addRow('ID валюты:', self.input_item)
        layout.addRow('Цена:', self.input_amount)
        layout.addRow('Запас:', self.stock_amount)
        layout.addRow(self.autorefill)
        
        buttons = QHBoxLayout()
        ok_btn = QPushButton('OK')
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton('Отмена')
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        
        layout.addRow(buttons)
        self.setLayout(layout)

    def get_item(self):
        return {
            'OutputItem': self.output_item.value(),
            'OutputAmount': self.output_amount.value(),
            'InputItem': self.input_item.value(),
            'InputAmount': self.input_amount.value(),
            'StockAmount': self.stock_amount.value(),
            'Autorefill': self.autorefill.isChecked()
        }

class CurrencyTracker(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        
        # Создаем вкладки
        tabs = QTabWidget()
        
        # Вкладка статистики
        stats_tab = QWidget()
        stats_layout = QVBoxLayout()
        
        # Добавляем поиск
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Поиск игрока...')
        self.search_input.textChanged.connect(self.search_player)
        
        # Кнопка сброса поиска
        self.clear_search_btn = QPushButton('Очистить')
        self.clear_search_btn.clicked.connect(self.clear_search)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.clear_search_btn)
        
        stats_layout.addLayout(search_layout)
        
        # Создаем TreeWidget для отображения токенов
        self.tokens_tree = QTreeWidget()
        self.tokens_tree.setHeaderLabels(['Игрок', 'Токены'])
        self.tokens_tree.setAlternatingRowColors(True)
        self.tokens_tree.setSortingEnabled(True)
        self.tokens_tree.setColumnCount(2)
        
        # Настраиваем размеры колонок
        header = self.tokens_tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        
        # Создаем группы для разных диапазонов токенов
        self.groups = {
            '2000+': QTreeWidgetItem(self.tokens_tree, ['2000+ токенов']),
            '1000-1999': QTreeWidgetItem(self.tokens_tree, ['1000-1999 токенов']),
            '500-999': QTreeWidgetItem(self.tokens_tree, ['500-999 токенов']),
            '100-499': QTreeWidgetItem(self.tokens_tree, ['100-499 токенов']),
            '1-99': QTreeWidgetItem(self.tokens_tree, ['1-99 токенов']),
            '0': QTreeWidgetItem(self.tokens_tree, ['0 токенов'])
        }
        
        for group in self.groups.values():
            group.setExpanded(True)
        
        stats_layout.addWidget(self.tokens_tree)
        stats_tab.setLayout(stats_layout)
        
        # Вкладка лога
        log_tab = QWidget()
        log_layout = QVBoxLayout()
        
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(6)
        self.log_table.setHorizontalHeaderLabels(['От', 'Кому', 'Метод', 'Кем', 'Тип', 'Количество'])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        log_layout.addWidget(self.log_table)
        log_tab.setLayout(log_layout)
        
        # Добавляем вкладки
        tabs.addTab(stats_tab, "Статистика")
        tabs.addTab(log_tab, "Лог")
        
        layout.addWidget(tabs)
        self.setLayout(layout)

    def load_data(self, tokens_data, log_data):
        # Очищаем все группы
        for group in self.groups.values():
            group.takeChildren()
        
        # Сортируем данные по количеству токенов
        sorted_data = sorted(tokens_data, key=lambda x: x['Tokens'], reverse=True)
        
        # Распределяем игроков по группам
        for entry in sorted_data:
            tokens = entry['Tokens']
            player = entry['CharacterName']
            
            if tokens >= 2000:
                group = self.groups['2000+']
            elif tokens >= 1000:
                group = self.groups['1000-1999']
            elif tokens >= 500:
                group = self.groups['500-999']
            elif tokens >= 100:
                group = self.groups['100-499']
            elif tokens > 0:
                group = self.groups['1-99']
            else:
                group = self.groups['0']
            
            item = QTreeWidgetItem(group, [player, str(tokens)])
            item.setTextAlignment(1, Qt.AlignRight)
        
        # Обновляем заголовки групп с количеством игроков
        for group_name, group in self.groups.items():
            count = group.childCount()
            if count > 0:
                group.setText(0, f'{group_name} ({count} игроков)')
        
        # Загрузка лога
        self.log_table.setRowCount(len(log_data))
        for i, entry in enumerate(log_data):
            self.log_table.setItem(i, 0, QTableWidgetItem(entry['From']))
            self.log_table.setItem(i, 1, QTableWidgetItem(entry['To']))
            self.log_table.setItem(i, 2, QTableWidgetItem(entry['Method']))
            self.log_table.setItem(i, 3, QTableWidgetItem(entry['By']))
            self.log_table.setItem(i, 4, QTableWidgetItem(entry['Type']))
            self.log_table.setItem(i, 5, QTableWidgetItem(str(entry['Amount'])))

    def search_player(self):
        search_text = self.search_input.text().lower()
        
        # Показываем все группы при пустом поиске
        if not search_text:
            for group in self.groups.values():
                group.setHidden(False)
                for i in range(group.childCount()):
                    group.child(i).setHidden(False)
            return
        
        # Проходим по всем группам и их элементам
        for group in self.groups.values():
            has_visible_children = False
            for i in range(group.childCount()):
                child = group.child(i)
                player_name = child.text(0).lower()
                # Показываем элемент, если имя содержит поисковый текст
                matches = search_text in player_name
                child.setHidden(not matches)
                has_visible_children = has_visible_children or matches
            
            # Показываем группу только если в ней есть видимые элементы
            group.setHidden(not has_visible_children)

    def clear_search(self):
        self.search_input.clear()
        self.search_player()

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

class ChatLogViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        
        # Создаем таблицу для лога
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['Время', 'Тип', 'Отправитель', 'Сообщение'])
        
        # Настраиваем заголовки и размеры столбцов
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Фиксированная ширина для времени
        header.setSectionResizeMode(1, QHeaderView.Fixed)  # Фиксированная ширина для типа
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # Фиксированная ширина для отправителя
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Растягиваемая ширина для сообщения
        
        # Устанавливаем начальные размеры столбцов
        self.table.setColumnWidth(0, 100)  # Время
        self.table.setColumnWidth(1, 100)  # Тип
        self.table.setColumnWidth(2, 150)  # Отправитель
        
        # Включаем перенос текста
        self.table.setWordWrap(True)
        
        # Автоматическая высота строк
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        
        # Создаем чекбоксы для фильтрации
        filter_layout = QHBoxLayout()
        self.filters = {
            'Global': QCheckBox('Глобальный'),
            'Team': QCheckBox('Команда'),
            'Local': QCheckBox('Локальный'),
            'Whisper': QCheckBox('Личные сообщения'),
            'Commands': QCheckBox('Команды'),
            'Players': QCheckBox('Игроки'),
            'Killfeed': QCheckBox('Килфид')
        }
        
        for checkbox in self.filters.values():
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self.apply_filters)
            filter_layout.addWidget(checkbox)
        
        # Кнопка обновления
        self.refresh_btn = QPushButton('Обновить')
        self.refresh_btn.clicked.connect(self.refresh_log)
        filter_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(filter_layout)
        layout.addWidget(self.table)
        self.setLayout(layout)

    def parse_log_line(self, line):
        try:
            # Извлекаем временную метку из строки, если она есть
            timestamp = ""
            if "[" in line and "]" in line:
                time_part = line.split("]", 1)[0].strip("[")
                if ":" in time_part:
                    # Для сообщений с явным временем (например, [08:10:48])
                    if len(time_part.split()) > 1 and ":" in time_part.split()[-1]:
                        timestamp = time_part.split()[-1]
                    else:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                else:
                    timestamp = datetime.now().strftime("%H:%M:%S")
            
            if "[Info   :Bloodstone] [Chat]" in line:
                # Обработка сообщений чата
                chat_type = None
                if "[Global]" in line:
                    chat_type = "Global"
                elif "[Team]" in line:
                    chat_type = "Team"
                elif "[Local]" in line:
                    chat_type = "Local"
                elif "[Whisper]" in line:
                    chat_type = "Whisper"
                else:
                    return None
                
                # Извлекаем имя отправителя и сообщение
                message_part = line.split("[Chat]")[1].strip()
                # Удаляем тип чата
                message_part = message_part.split("]", 1)[1].strip()
                if ":" in message_part:
                    sender, message = message_part.split(":", 1)
                    return timestamp, chat_type, sender.strip(), message.strip()
                return None
                
            elif "[Info   :KindredCommands]" in line:
                if "Player" in line:
                    message = line.split("KindredCommands]")[1].strip()
                    return timestamp, "Players", "System", message
                else:
                    message = line.split("KindredCommands]")[1].strip()
                    return timestamp, "Commands", "System", message
                
            elif "[Message:  Killfeed]" in line or "[Warning:  Killfeed]" in line or \
                 ("[Info   :  Killfeed]" in line and "killed" in line.lower()):
                message = line.split("Killfeed]")[1].strip()
                return timestamp, "Killfeed", "System", message
                
        except Exception as e:
            print(f"Error parsing line: {str(e)}")  # Для отладки
            pass
        return None

    def load_log(self, log_text):
        self.all_entries = []
        for line in log_text.split('\n'):
            parsed = self.parse_log_line(line)
            if parsed:
                self.all_entries.append(parsed)
        self.apply_filters()

    def apply_filters(self):
        self.table.setRowCount(0)
        row = 0
        for entry in self.all_entries:
            if entry[1] in self.filters and self.filters[entry[1]].isChecked():
                self.table.insertRow(row)
                for col, value in enumerate(entry):
                    item = QTableWidgetItem(str(value))
                    if col == 3:  # Столбец с сообщением
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
                    else:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self.table.setItem(row, col, item)
                row += 1
        
        # Обновляем высоту строк после добавления данных
        self.table.resizeRowsToContents()

    def refresh_log(self):
        if self.parent and hasattr(self.parent, 'load_chat_log'):
            self.parent.load_chat_log()

class BossEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.bosses = []
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        
        # Список боссов
        boss_layout = QHBoxLayout()
        self.boss_list = QComboBox()
        self.boss_list.currentIndexChanged.connect(self.load_boss_data)
        
        self.add_boss_btn = QPushButton('Добавить босса')
        self.add_boss_btn.clicked.connect(self.add_boss)
        self.remove_boss_btn = QPushButton('Удалить босса')
        self.remove_boss_btn.clicked.connect(self.remove_boss)
        
        boss_layout.addWidget(QLabel('Босс:'))
        boss_layout.addWidget(self.boss_list)
        boss_layout.addWidget(self.add_boss_btn)
        boss_layout.addWidget(self.remove_boss_btn)
        
        # Основные настройки босса
        form_layout = QFormLayout()
        
        self.name_input = QLineEdit()
        self.name_hash = QLineEdit()
        self.asset_name = QLineEdit()
        self.prefab_guid = QSpinBox()
        self.prefab_guid.setRange(-2147483648, 2147483647)
        
        self.spawn_hour = QLineEdit()
        self.despawn_hour = QLineEdit()
        self.level = QSpinBox()
        self.level.setRange(0, 999)
        self.multiplier = QDoubleSpinBox()
        self.multiplier.setRange(0, 100)
        
        self.boss_spawn = QCheckBox('Босс активен')
        self.lifetime = QSpinBox()
        self.lifetime.setRange(0, 999999)
        
        # Координаты
        self.pos_x = QDoubleSpinBox()
        self.pos_x.setRange(-10000, 10000)
        self.pos_x.setDecimals(6)
        self.pos_y = QDoubleSpinBox()
        self.pos_y.setRange(-10000, 10000)
        self.pos_y.setDecimals(6)
        self.pos_z = QDoubleSpinBox()
        self.pos_z.setRange(-10000, 10000)
        self.pos_z.setDecimals(6)
        
        form_layout.addRow('Имя:', self.name_input)
        form_layout.addRow('Hash:', self.name_hash)
        form_layout.addRow('Asset Name:', self.asset_name)
        form_layout.addRow('PrefabGUID:', self.prefab_guid)
        form_layout.addRow('Время появления:', self.spawn_hour)
        form_layout.addRow('Время исчезновения:', self.despawn_hour)
        form_layout.addRow('Уровень:', self.level)
        form_layout.addRow('Множитель:', self.multiplier)
        form_layout.addRow(self.boss_spawn)
        form_layout.addRow('Время жизни:', self.lifetime)
        form_layout.addRow('X:', self.pos_x)
        form_layout.addRow('Y:', self.pos_y)
        form_layout.addRow('Z:', self.pos_z)
        
        # Таблица предметов
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(5)
        self.items_table.setHorizontalHeaderLabels(['Название', 'ID предмета', 'Количество', 'Шанс', 'Цвет'])
        header = self.items_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        
        # Кнопки управления предметами
        items_btn_layout = QHBoxLayout()
        self.add_item_btn = QPushButton('Добавить предмет')
        self.add_item_btn.clicked.connect(self.add_item)
        self.remove_item_btn = QPushButton('Удалить предмет')
        self.remove_item_btn.clicked.connect(self.remove_item)
        
        items_btn_layout.addWidget(self.add_item_btn)
        items_btn_layout.addWidget(self.remove_item_btn)
        
        # Добавляем все элементы в основной layout
        layout.addLayout(boss_layout)
        layout.addLayout(form_layout)
        layout.addWidget(QLabel('Предметы:'))
        layout.addWidget(self.items_table)
        layout.addLayout(items_btn_layout)
        
        self.setLayout(layout)

    def load_bosses(self, bosses_data):
        self.bosses = bosses_data
        self.boss_list.clear()
        for boss in bosses_data:
            self.boss_list.addItem(boss['name'])
        if bosses_data:
            self.load_boss_data(0)

    def load_boss_data(self, index):
        if index < 0 or not self.bosses:
            return
            
        boss = self.bosses[index]
        
        # Загружаем основные данные
        self.name_input.setText(boss['name'])
        self.name_hash.setText(boss['nameHash'])
        self.asset_name.setText(boss['AssetName'])
        self.prefab_guid.setValue(boss['PrefabGUID'])
        self.spawn_hour.setText(boss['Hour'])
        self.despawn_hour.setText(boss['HourDespawn'])
        self.level.setValue(boss['level'])
        self.multiplier.setValue(boss['multiplier'])
        self.boss_spawn.setChecked(boss['bossSpawn'])
        self.lifetime.setValue(boss['Lifetime'])
        self.pos_x.setValue(boss['x'])
        self.pos_y.setValue(boss['y'])
        self.pos_z.setValue(boss['z'])
        
        # Загружаем предметы
        self.items_table.setRowCount(len(boss['items']))
        for row, item in enumerate(boss['items']):
            self.items_table.setItem(row, 0, QTableWidgetItem(item['name']))
            self.items_table.setItem(row, 1, QTableWidgetItem(str(item['ItemID'])))
            self.items_table.setItem(row, 2, QTableWidgetItem(str(item['Stack'])))
            self.items_table.setItem(row, 3, QTableWidgetItem(str(item['Chance'])))
            self.items_table.setItem(row, 4, QTableWidgetItem(item['Color']))

    def get_current_boss_data(self):
        if self.boss_list.currentIndex() < 0:
            return None
            
        items = []
        for row in range(self.items_table.rowCount()):
            items.append({
                'name': self.items_table.item(row, 0).text(),
                'ItemID': int(self.items_table.item(row, 1).text()),
                'Stack': int(self.items_table.item(row, 2).text()),
                'Chance': int(self.items_table.item(row, 3).text()),
                'Color': self.items_table.item(row, 4).text()
            })
        
        return {
            'name': self.name_input.text(),
            'nameHash': self.name_hash.text(),
            'AssetName': self.asset_name.text(),
            'Hour': self.spawn_hour.text(),
            'HourDespawn': self.despawn_hour.text(),
            'PrefabGUID': self.prefab_guid.value(),
            'level': self.level.value(),
            'multiplier': self.multiplier.value(),
            'items': items,
            'bossSpawn': self.boss_spawn.isChecked(),
            'Lifetime': self.lifetime.value(),
            'x': self.pos_x.value(),
            'y': self.pos_y.value(),
            'z': self.pos_z.value()
        }

    def add_boss(self):
        name, ok = QInputDialog.getText(self, 'Новый босс', 'Имя босса:')
        if ok and name:
            new_boss = {
                'name': name,
                'nameHash': '0',
                'AssetName': '',
                'Hour': '00:00',
                'HourDespawn': '00:30',
                'PrefabGUID': 0,
                'level': 100,
                'multiplier': 1,
                'items': [],
                'bossSpawn': False,
                'Lifetime': 1800,
                'x': 0,
                'y': 0,
                'z': 0
            }
            self.bosses.append(new_boss)
            self.boss_list.addItem(name)
            self.boss_list.setCurrentIndex(len(self.bosses) - 1)

    def remove_boss(self):
        current_index = self.boss_list.currentIndex()
        if current_index >= 0:
            self.bosses.pop(current_index)
            self.boss_list.removeItem(current_index)
            if self.bosses:
                self.load_boss_data(0)

    def add_item(self):
        row = self.items_table.rowCount()
        self.items_table.insertRow(row)
        self.items_table.setItem(row, 0, QTableWidgetItem('Новый предмет'))
        self.items_table.setItem(row, 1, QTableWidgetItem('0'))
        self.items_table.setItem(row, 2, QTableWidgetItem('1'))
        self.items_table.setItem(row, 3, QTableWidgetItem('100'))
        self.items_table.setItem(row, 4, QTableWidgetItem('#daa520'))

    def remove_item(self):
        current_row = self.items_table.currentRow()
        if current_row >= 0:
            self.items_table.removeRow(current_row)

    def get_bosses(self):
        # Сохраняем текущие изменения
        current_index = self.boss_list.currentIndex()
        if current_index >= 0:
            self.bosses[current_index] = self.get_current_boss_data()
        return self.bosses

class RaidEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        
        # Создаем вкладки для разных настроек рейдов
        tabs = QTabWidget()
        
        # Вкладка RaidForge
        raid_forge_tab = QWidget()
        raid_forge_layout = QVBoxLayout()
        
        # Основные настройки RaidForge
        forge_form = QFormLayout()
        
        self.override_mode = QComboBox()
        self.override_mode.addItems(['Normal', 'ForceOn', 'ForceOff'])
        
        self.raid_check_interval = QSpinBox()
        self.raid_check_interval.setRange(1, 3600)
        
        forge_form.addRow('Режим рейдов:', self.override_mode)
        forge_form.addRow('Интервал проверки (сек):', self.raid_check_interval)
        
        # Таблица расписания
        self.schedule_table = QTableWidget()
        self.schedule_table.setColumnCount(3)
        self.schedule_table.setRowCount(7)
        self.schedule_table.setHorizontalHeaderLabels(['День', 'Начало', 'Конец'])
        
        days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        for i, day in enumerate(days):
            self.schedule_table.setItem(i, 0, QTableWidgetItem(day))
            start_time = QLineEdit()
            start_time.setInputMask('99:99:99')
            end_time = QLineEdit()
            end_time.setInputMask('99:99:99')
            self.schedule_table.setCellWidget(i, 1, start_time)
            self.schedule_table.setCellWidget(i, 2, end_time)
        
        header = self.schedule_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        
        raid_forge_layout.addLayout(forge_form)
        raid_forge_layout.addWidget(QLabel('Расписание рейдов:'))
        raid_forge_layout.addWidget(self.schedule_table)
        raid_forge_tab.setLayout(raid_forge_layout)
        
        # Вкладка RaidGuard
        raid_guard_tab = QWidget()
        guard_layout = QFormLayout()
        
        self.raid_guard = QCheckBox('Включить защиту рейдов')
        self.alliances = QCheckBox('Разрешить альянсы')
        self.clan_based = QCheckBox('Клановые альянсы')
        self.friendly_fire = QCheckBox('Запретить урон по союзникам')
        
        self.max_alliance_size = QSpinBox()
        self.max_alliance_size.setRange(1, 100)
        
        self.limit_assists = QCheckBox('Ограничить помощь в рейдах')
        self.alliance_assists = QSpinBox()
        self.alliance_assists.setRange(1, 100)
        
        guard_layout.addRow(self.raid_guard)
        guard_layout.addRow(self.alliances)
        guard_layout.addRow(self.clan_based)
        guard_layout.addRow(self.friendly_fire)
        guard_layout.addRow('Макс. размер альянса:', self.max_alliance_size)
        guard_layout.addRow(self.limit_assists)
        guard_layout.addRow('Макс. количество помощников:', self.alliance_assists)
        
        raid_guard_tab.setLayout(guard_layout)
        
        # Добавляем вкладки
        tabs.addTab(raid_forge_tab, 'Расписание')
        tabs.addTab(raid_guard_tab, 'Защита')
        
        layout.addWidget(tabs)
        self.setLayout(layout)

    def load_raid_forge(self, config_text):
        # Парсим конфиг RaidForge
        for line in config_text.splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                if key == 'OverrideMode':
                    self.override_mode.setCurrentText(value)
                elif key == 'RaidCheckInterval':
                    self.raid_check_interval.setValue(int(value))
                elif 'Start' in key or 'End' in key:
                    day = key.replace('Start', '').replace('End', '')
                    day_index = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].index(day)
                    col = 1 if 'Start' in key else 2
                    self.schedule_table.cellWidget(day_index, col).setText(value)

    def load_raid_guard(self, config_text):
        # Парсим конфиг RaidGuard
        for line in config_text.splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().lower()
                
                if key == 'RaidGuard':
                    self.raid_guard.setChecked(value == 'true')
                elif key == 'Alliances':
                    self.alliances.setChecked(value == 'true')
                elif key == 'ClanBasedAlliances':
                    self.clan_based.setChecked(value == 'true')
                elif key == 'PreventFriendlyFire':
                    self.friendly_fire.setChecked(value == 'true')
                elif key == 'MaxAllianceSize':
                    self.max_alliance_size.setValue(int(value))
                elif key == 'LimitAssists':
                    self.limit_assists.setChecked(value == 'true')
                elif key == 'AllianceAssists':
                    self.alliance_assists.setValue(int(value))

    def get_raid_forge_config(self):
        config = []
        config.append('[RaidSchedule]')
        config.append(f'OverrideMode = {self.override_mode.currentText()}')
        config.append(f'RaidCheckInterval = {self.raid_check_interval.value()}')
        
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for i, day in enumerate(days):
            start = self.schedule_table.cellWidget(i, 1).text()
            end = self.schedule_table.cellWidget(i, 2).text()
            config.append(f'{day}Start = {start}')
            config.append(f'{day}End = {end}')
        
        return '\n'.join(config)

    def get_raid_guard_config(self):
        config = []
        config.append('[Config]')
        config.append(f'RaidGuard = {str(self.raid_guard.isChecked()).lower()}')
        config.append(f'Alliances = {str(self.alliances.isChecked()).lower()}')
        config.append(f'ClanBasedAlliances = {str(self.clan_based.isChecked()).lower()}')
        config.append(f'PreventFriendlyFire = {str(self.friendly_fire.isChecked()).lower()}')
        config.append(f'MaxAllianceSize = {self.max_alliance_size.value()}')
        config.append(f'LimitAssists = {str(self.limit_assists.isChecked()).lower()}')
        config.append(f'AllianceAssists = {self.alliance_assists.value()}')
        
        return '\n'.join(config)

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
        self.chat_log_viewer = ChatLogViewer(self)
        self.boss_editor = BossEditor()
        self.raid_editor = RaidEditor()
        
        self.tabs.addTab(self.ftp_connection, 'FTP подключение')
        self.tabs.addTab(self.config_editor, 'Настройки')
        self.tabs.addTab(self.products_editor, 'Магазин')
        self.tabs.addTab(self.currency_tracker, 'Статистика')
        self.tabs.addTab(self.announcement_editor, 'Анонсы')
        self.tabs.addTab(self.chat_log_viewer, 'Чат лог')
        self.tabs.addTab(self.boss_editor, 'Редактор боссов')
        self.tabs.addTab(self.raid_editor, 'Настройки рейдов')
        
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
            merchants_path = '/BepInEx/config/BloodyMerchant/merchants.json'
            tokens_path = '/BepInEx/config/BloodyWallet/tokens.json'
            log_path = '/BepInEx/config/BloodyWallet/log.json'
            announcements_path = '/BepInEx/config/KindredCommands/announcements.json'

            # Загрузка BloodyRewards.cfg
            with BytesIO() as f:
                self.ftp.retrbinary(f'RETR {config_path}', f.write)
                self.config_editor.load_config(f.getvalue().decode('utf-8'))
            
            # Загрузка merchants.json
            with BytesIO() as f:
                self.ftp.retrbinary(f'RETR {merchants_path}', f.write)
                merchants = json.loads(f.getvalue().decode('utf-8'))
                self.products_editor.load_merchants(merchants)

            # Загрузка tokens.json и log.json
            with BytesIO() as f:
                self.ftp.retrbinary(f'RETR {tokens_path}', f.write)
                tokens_data = json.loads(f.getvalue().decode('utf-8'))
                
            with BytesIO() as f:
                self.ftp.retrbinary(f'RETR {log_path}', f.write)
                log_data = json.loads(f.getvalue().decode('utf-8'))
                
            self.currency_tracker.load_data(tokens_data, log_data)

            # Загрузка announcements.json
            with BytesIO() as f:
                self.ftp.retrbinary(f'RETR {announcements_path}', f.write)
                announcements = json.loads(f.getvalue().decode('utf-8'))
                self.announcement_editor.load_announcements(announcements)
            
            # Добавляем загрузку лога чата
            self.load_chat_log()
            
            # Загрузка bosses.json
            bosses_path = '/BepInEx/config/BloodyBoss/Bosses.json'
            with BytesIO() as f:
                self.ftp.retrbinary(f'RETR {bosses_path}', f.write)
                bosses = json.loads(f.getvalue().decode('utf-8'))
                self.boss_editor.load_bosses(bosses)
            
            # Загрузка настроек рейдов
            raid_forge_path = '/BepInEx/config/RaidForge.cfg'
            raid_guard_path = '/BepInEx/config/io.zfolmt.RaidGuard.cfg'
            
            with BytesIO() as f:
                self.ftp.retrbinary(f'RETR {raid_forge_path}', f.write)
                self.raid_editor.load_raid_forge(f.getvalue().decode('utf-8'))
            
            with BytesIO() as f:
                self.ftp.retrbinary(f'RETR {raid_guard_path}', f.write)
                self.raid_editor.load_raid_guard(f.getvalue().decode('utf-8'))
        
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка загрузки файлов: {str(e)}')

    def load_chat_log(self):
        try:
            log_path = '/BepInEx/LogOutput.log'
            with BytesIO() as f:
                self.ftp.retrbinary(f'RETR {log_path}', f.write)
                log_text = f.getvalue().decode('utf-8', errors='ignore')
                self.chat_log_viewer.load_log(log_text)
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка загрузки лога чата: {str(e)}')

    def save_all(self):
        if not self.ftp:
            QMessageBox.critical(self, 'Ошибка', 'FTP соединение потеряно. Пожалуйста, переподключитесь.')
            return
            
        try:
            # Проверяем FTP соединение
            try:
                self.ftp.voidcmd("NOOP")
            except:
                # Если соединение разорвано, пытаемся переподключиться
                self.ftp_connection.connect_ftp()
                
            config_path = '/BepInEx/config/BloodyRewards.cfg'
            merchants_path = '/BepInEx/config/BloodyMerchant/merchants.json'
            announcements_path = '/BepInEx/config/KindredCommands/announcements.json'

            # Сохранение BloodyRewards.cfg
            config_data = self.config_editor.get_config().encode('utf-8')
            with BytesIO(config_data) as f:
                self.ftp.storbinary(f'STOR {config_path}', f)
            
            # Сохранение merchants.json
            merchants_data = json.dumps(self.products_editor.get_merchants(), indent=2).encode('utf-8')
            with BytesIO(merchants_data) as f:
                self.ftp.storbinary(f'STOR {merchants_path}', f)
            
            # Сохранение announcements.json
            announcements_data = json.dumps(self.announcement_editor.get_announcements(), indent=2).encode('utf-8')
            with BytesIO(announcements_data) as f:
                self.ftp.storbinary(f'STOR {announcements_path}', f)
            
            # Сохранение bosses.json
            bosses_path = '/BepInEx/config/BloodyBoss/Bosses.json'
            bosses_data = json.dumps(self.boss_editor.get_bosses(), indent=2).encode('utf-8')
            with BytesIO(bosses_data) as f:
                self.ftp.storbinary(f'STOR {bosses_path}', f)
            
            # Сохранение настроек рейдов
            raid_forge_path = '/BepInEx/config/RaidForge.cfg'
            raid_guard_path = '/BepInEx/config/io.zfolmt.RaidGuard.cfg'
            
            raid_forge_data = self.raid_editor.get_raid_forge_config().encode('utf-8')
            with BytesIO(raid_forge_data) as f:
                self.ftp.storbinary(f'STOR {raid_forge_path}', f)
            
            raid_guard_data = self.raid_editor.get_raid_guard_config().encode('utf-8')
            with BytesIO(raid_guard_data) as f:
                self.ftp.storbinary(f'STOR {raid_guard_path}', f)
            
            QMessageBox.information(self, 'Успех', 'Все изменения сохранены!')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка сохранения: {str(e)}')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
