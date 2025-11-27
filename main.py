#!/usr/bin/python3
import kivy
kivy.require('2.1.0')
import os

from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.slider import Slider
from kivy.utils import platform
from kivy.config import Config
from kivy.core.window import Window
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.metrics import dp
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.graphics import Color, Rectangle, Line
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.uix.popup import Popup
from kivy.clock import Clock, mainthread
from threading import Thread
import time

if platform=="android":
	from android.permissions import request_permissions, Permission, check_permission
	from android.storage import primary_external_storage_path
	from jnius import autoclass
	request_permissions([Permission.READ_EXTERNAL_STORAGE])
	def request_manage_external_storage():
		Intent = autoclass('android.content.Intent')
		Settings = autoclass('android.provider.Settings')
		Uri = autoclass('android.net.Uri')
		PythonActivity = autoclass('org.kivy.android.PythonActivity')
		Environment = autoclass('android.os.Environment')
		# Check if MANAGE_EXTERNAL_STORAGE is already granted
#		if Settings.canDrawOverlays(PythonActivity.mActivity): # This is a common check for special permissions
		if Environment.isExternalStorageManager():
			print("MANAGE_EXTERNAL_STORAGE already granted")
			return
		# Create an intent to open the "All files access" settings for your app
		intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
		intent.setData(Uri.parse("package:" + PythonActivity.mActivity.getPackageName()))
		PythonActivity.mActivity.startActivity(intent)
	request_manage_external_storage()
	root_path=primary_external_storage_path()
else:
	root_path="/"


selected_file=None
file_popup=None


class FNLabel (RecycleDataViewBehavior,Button):
	def __init__(self, **kwargs):
		super(FNLabel,self).__init__(**kwargs)
		self.halign="left"
		self.valign="middle"
		self.selected=False
		self.font_name='RobotoMono-Regular'

	def on_size(self, *args):
		self.text_size = self.size
	def on_touch_down(self, touch):
		global selected_file
		global file_popup
		if self.collide_point(*touch.pos):
			if touch.is_double_tap:
#				print(f"Double tapped on item: {self.text}")
				selected_file=self.text
				file_popup.select_file(None)
				return True
			return self.parent.select_node(self.index)
		return super().on_touch_down(touch)
	def refresh_view_attrs(self, rv, index, data):
		''' Called by the RecycleView to update the view's attributes. '''
		self.index = index
		self.text = data['text']
		return super(FNLabel, self).refresh_view_attrs(rv, index, data)

	def apply_selection(self, rv, index, is_selected):
		''' Respond to the selection of items in the view. '''
		global selected_file
		self.selected = is_selected
		if is_selected:
			self.background_color = (0.1, 0.5, 0.8, 1) # Highlight selected
			print(f"Selection changed to {rv.data[index]['text']}")
			selected_file=rv.data[index]['text']
		else:
			self.background_color = (0.2, 0.2, 0.2, 1) # Default color
#			print(f"Selection removed for {rv.data[index]['text']}")

class SelectableRecycleBoxLayout(FocusBehavior, LayoutSelectionBehavior,
                                 RecycleBoxLayout):
	pass



class AlLabel(Label):
   def on_size(self, *args):
      self.text_size = self.size

class MyFileChooserPopup(Popup):
	def __init__(self, select_callback, path, **kwargs):
		super().__init__(**kwargs)
		self.title = "Select a File"
		self.select_callback = select_callback
		self.path=path
		self.selected=None
		self.fns=None
		# Create the FileChooser widget
		recycle_box_layout = SelectableRecycleBoxLayout(default_size=(None, dp(32)), default_size_hint=(1, None),
											  size_hint=(1, None), orientation='vertical')
		recycle_box_layout.bind(minimum_height=recycle_box_layout.setter("height"))
		self.recycle_view = RecycleView()
		self.recycle_view.add_widget(recycle_box_layout)
		self.recycle_view.viewclass = 'FNLabel'

		# Create buttons for the popup
		button_layout = BoxLayout(size_hint_y=None, height=48)
		select_button = Button(text="Открыть", on_press=self.select_file)
		cancel_button = Button(text="Отмена", on_press=self.dismiss)
		button_layout.add_widget(select_button)
		button_layout.add_widget(cancel_button)

		self.filter_text=TextInput(text="",size_hint_y=None,height=dp(32))
		self.filter_text.bind(text=self.on_filter_change)
		# Create the main content layout
		content_layout = BoxLayout(orientation='vertical')
		content_layout.add_widget(self.filter_text)
#		content_layout.add_widget(self.file_chooser)
		content_layout.add_widget(self.recycle_view)
		content_layout.add_widget(button_layout)
		self.content = content_layout
		self.update_path(self.path)

	def select_file(self, instance):
		global selected_file
		print(selected_file)
		if (selected_file!=None) and (len(selected_file)>0):
			if selected_file=='[..]':
				self.path=os.path.dirname(self.path)
				self.update_path(self.path)
			else:
				if selected_file[0]=='[' and selected_file[-1]==']':
					self.path=os.path.join(self.path,selected_file[1:-1])
					self.update_path(self.path)
				else:
					self.select_callback(os.path.join(self.path,selected_file))

	def get_filtered(self):
		flt=self.filter_text.text.strip().lower()
		filtered=[ f for f  in self.fns if ((flt in f.lower()) or ((f[0]=='[') and (f[-1]==']')))]
		return filtered

	def on_filter_change(self,instance,value):
		if len(self.filter_text.text.strip())>0:
			fns=self.get_filtered()
		else:
			fns=self.fns
		self.recycle_view.data = [{'text': x} for x in fns]

	def update_path(self,path):
		global root_path
		if path==root_path:
			dirs=[]
		else:
			dirs=["[..]"]
		files=[]
		with os.scandir(path) as entries:
			for entry in entries:
				if entry.is_dir(): dirs.append(f"[{entry.name}]")
				if entry.is_file(): files.append(entry.name)
		dirs.sort()
		files.sort()
		self.fns=dirs+files
		if len(self.filter_text.text.strip())>0:
			fns=self.get_filtered()
		else:
			fns=self.fns
		self.recycle_view.data = [{'text': x} for x in fns]
		self.title=path



class MyApp(App):
	def build(self):
		global root_path
		self.path=root_path
		self.bindata=None
		self.status=0 # 0-файл не выбран, 1-файл выбран, 2-подготовлен wav, 3-воспроизведение
		self.wav_data=None
		self.current_chunk=0
		self.total_chunks=0
		self.chunk_size=4096
		self.pos_percent=0
		self.srate=16000
		self.title = 'БК0010 Магнитофон'

		vbox1=BoxLayout(orientation="vertical")
		self.select_file_button=Button(text="Файл...")
		self.selected_file_label=Label(text="Не выбран")
		self.select_file_button.bind(on_press=self.select_file_button_pressed)
		grid1=GridLayout(cols=2)
		grid1.add_widget(Label(text=" "))
		grid1.add_widget(Label(text=" "))
		grid1.add_widget(self.select_file_button)
		grid1.add_widget(self.selected_file_label)
		name_label_box=BoxLayout(orientation="horizontal",height=60,size_hint_y=None)
		name_label_box.add_widget(AlLabel(text="Имя:", halign="left",valign="middle"))
		self.name_checkbox=CheckBox(active=False,size_hint=(None,1))
		self.name_checkbox.bind(active=self.name_checkbox_pressed)
		name_label_box.add_widget(self.name_checkbox)
		grid1.add_widget(name_label_box)
		self.int_name_text=TextInput(multiline=False, font_size=32,font_name='RobotoMono-Regular',height=60,size_hint_y=None,disabled=True)
		self.int_name_text.bind(on_text_validate=self.adr_changed)
		grid1.add_widget(self.int_name_text)
		grid1.add_widget(AlLabel(text="Адрес загрузки (8):", halign="left",valign="middle",height=60,size_hint_y=None))
		self.adr_text=TextInput(multiline=False, font_size=32,font_name='RobotoMono-Regular',input_filter='int',height=60,size_hint_y=None)
		self.adr_text.bind(on_text_validate=self.adr_changed)
		grid1.add_widget(self.adr_text)
		grid1.add_widget(AlLabel(text="Длина файла:", halign="left",valign="middle",height=60,size_hint_y=None))
		self.len_text=TextInput(multiline=False, font_size=32,font_name='RobotoMono-Regular',input_filter='int',disabled=False,height=60,size_hint_y=None)
		grid1.add_widget(self.len_text)
		grid1.add_widget(AlLabel(text="Турбо загрузчик:", halign="left",valign="middle",height=60,size_hint_y=None))
		self.turbo_checkbox=CheckBox(active=True,height=60,size_hint_y=None)
		self.turbo_checkbox.bind(active=self.turbo_checkbox_pressed)
		grid1.add_widget(self.turbo_checkbox)
		self.button_start=Button(text="Старт", disabled=True)
		self.button_start.bind(on_press=self.on_start_button_pressed)
		grid1.add_widget(self.button_start)
		self.button_stop=Button(text="Стоп", disabled=True)
		self.button_stop.bind(on_press=self.on_stop_button_pressed)
		grid1.add_widget(self.button_stop)
		grid1.add_widget(Label(text=""))
		vbox1.add_widget(grid1)
		self.progress_slider=Slider(min=0,max=100,value=0,value_track=True,size_hint_y=None)
		self.progress_slider.bind(value=self.on_progress_slider_change)
		vbox1.add_widget(self.progress_slider)
		self.console_text=TextInput(multiline=True, font_size=10,font_name='RobotoMono-Regular', foreground_color=(0,1,0), background_color=(0.2,0.2,0.2),readonly=True)
		vbox1.add_widget(self.console_text)
		return vbox1

	def show_file_chooser(self):
		global file_popup
		file_popup = MyFileChooserPopup(select_callback=self.file_selected, path=self.path, size_hint=(0.9, 0.9))
		file_popup.open()
	@mainthread
	def print(self,txt):
		self.console_text.text+="\n%s" %(str(txt))
	def select_file_button_pressed(self,event):
		self.print("Выбор файла")
		self.show_file_chooser()

	def name_checkbox_pressed(self,checkbox,value):
		self.int_name_text.disabled=not(value)
		if self.status==2: self.status=1

	def adr_changed(self,instance):
		if self.status==2: self.status=1
	def on_start_button_pressed(self,event):
		if self.status<1: return
		if self.status==1:
			self.prepare_wav()
			self.status=2
		self.button_start.disabled=True
		self.button_stop.disabled=False
		if self.progress_slider.value>90:
			self.progress_slider.value=0
		self.status=3
		if platform=="android":
			audio_thread = Thread(target=self.play_thread)
			audio_thread.daemon = True # Allows the thread to exit when the main program exits
			audio_thread.start()


	def on_stop_button_pressed(self,event):
		self.current_chunk=self.total_chunks-1

	def turbo_checkbox_pressed(self,checkbox,value):
		if self.status==2: self.status=1

	def on_progress_slider_change(self,instance,value):
		if value==self.pos_percent: return
		self.current_chunk=int(self.total_chunks*(value/100))


	def file_selected(self,selection):
		global file_popup
		file_popup.dismiss()
		self.path=os.path.dirname(selection)
		self.print(f"Открытие {selection}")
		try:
			with open(selection, "rb") as binfile:
				bin_data=binfile.read()
				self.parse_bin(bin_data)
		except FileNotFoundError:
			self.print("Ошибка открытия файла.")
	def handle_chooser_result(self,result):
		self.print(result)
	def parse_bin(self,data):
		global selected_file
		ADDRESS_MIN = 0o320
		ADDRESS_MIN_TURBO = 0o600
		ADDRESS_MAX = 0o177600
		adr=data[0] | data[1]<<8
		lenght=data[2] | data[3]<<8
		self.selected_file_label.text=os.path.basename(selected_file)
		self.int_name_text.text=os.path.basename(selected_file).upper()
		self.adr_text.text="%o" %(adr)
		self.len_text.text="%d" %(lenght)
		if(lenght !=len(data)-4):
			self.print("!!! Длина файла не совпадает с заявленной !!!")
			self.print("Заявлено %d, прочитано %d" %(lenght,len(data)-4))
		if len(data)<5:
			self.print("Слишком короткий файл!")
			return
		if adr<ADDRESS_MIN_TURBO:
			self.turbo_checkbox.active=False
		if adr<ADDRESS_MIN and int(adr_text.text,base=8)<ADDRESS_MIN:
			self.print("Не правильный адрес загрузки (<%o)" % ADDRESS_MIN)
		self.bindata=data
		self.status=1
		self.button_start.disabled=False

	def prepare_wav(self):
		LEVEL_0=0
		LEVEL_1=255
		BIT_0 = (   LEVEL_1, LEVEL_1, LEVEL_0, LEVEL_0 )
		BIT_1 = (   LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1,  LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0 )
		TUNE =  (   LEVEL_1, LEVEL_1,   LEVEL_0, LEVEL_0 )
		AFTER_TUNE = (   LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1,  LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0 )
		SYNCHRO_SHORT = (   LEVEL_1, LEVEL_1,   LEVEL_0, )
		SYNCHRO_LONG = (   LEVEL_1, LEVEL_1,   LEVEL_0, LEVEL_0 )
		END=( LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1,  LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0)

		SAMPLE_RATE_10 = 21428
#		SAMPLE_RATE_11 = 25000
		SAMPLE_RATE_TURBO = 40000
		TUNE_COUNT = 4096
		TUNE_COUNT_SECOND = 10
		TUNE_COUNT_END = 200

		TURBO_TUNE_COUNT = 1024
		TURBO_TUNE_COUNT_END = 2

		TURBO_BIT_0 = (  LEVEL_1,   LEVEL_0, LEVEL_0 )
		TURBO_BIT_1 = (   LEVEL_1, LEVEL_1, LEVEL_1,   LEVEL_0, LEVEL_0 )
		TURBO_TUNE = (   LEVEL_1, LEVEL_1, LEVEL_1,   LEVEL_0, LEVEL_0, LEVEL_0 )
		TURBO_AFTER_TUNE = (	LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1, LEVEL_1,
								LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0, LEVEL_0 )
		# БКшный код загрузчика
		LOADER_CODE = [
						0o000760,			#0
						0o000302,			#2
						0o001000,			#4
						0o001000,			#6
						0o001000,			#8
						0o001000,			#10
						0o001000,			#12
						0o001000,			#14
						0o001000,			#16
						0o001000,			#18
						0o012701,	#1000	#20
						0o040000,	#1002	#22 <- LOADER_OFFSET_ADDRESS
						0o012700,	#1004   #24
						0o024102,	#1006   #26 <- LOADER_OFFSET_SIZE
						0o010137,	#1010	#28
						0o000322,	#1012	#30
						0o010037,	#1014	#32
						0o000324,	#1016	#34
						0o012704,	#1020	#36
						0o001106,	#1022	#38
						0o012705,	#1024	#40
						0o000400,	#1026	#42
						0o012425,	#1030	#44
						0o001376,	#1032	#46
						0o005002,	#1034	#48
						0o012703,	#1036	#50
						0o000400,	#1040	#52
						0o012704,	#1042	#54
						0o177716,	#1044	#56
						0o012705,	#1046	#58
						0o000040,	#1050	#60
						0o030514,	#1052	#62
						0o001376,	#1054	#64
						0o030514,	#1056	#66
						0o001776,	#1060	#68
						0o005202,	#1062	#70
						0o030514,	#1064	#72
						0o001375,	#1066	#74
						0o077306,	#1070	#76
						0o105002,	#1072	#78
						0o000302,	#1074	#80
						0o006302,	#1076	#82
						0o006302,	#1100	#84
						0o000137,	#1102	#86
						0o000400,	#1104	#88
						0o005003,	#400 	#90
						0o030514,	#402 	#92
						0o001776,	#404 	#94
						0o005203,	#406 	#96
						0o030514,	#410	#98
						0o001375,	#412	#100
						0o160203,	#414	#102
						0o100001,	#416	#104
						0o005403,	#420	#106
						0o020327,	#422	#108
						0o000006,	#424	#110
						0o003364,	#426	#112
						0o012703,	#430	#114
						0o000010,	#432	#116
						0o010302,	#434	#118
						0o030514,	#436	#120
						0o001776,	#440	#122
						0o030514,	#442	#124
						0o001410,	#444	#126
						0o030514,	#446	#128
						0o001406,	#450	#130
						0o030514,	#452	#132
						0o001404,	#454	#134
						0o030514,	#456	#136
						0o001376,	#460	#138
						0o000261,	#462	#140
						0o000401,	#464	#142
						0o000241,	#466	#144
						0o106011,	#500	#146
						0o077217,	#502	#148
						0o005201,	#504	#150
						0o077022,	#506	#152
						0o013705,	#510	#154
						0o000322,	#512	#156
						0o010503,	#514	#158
						0o013704,	#516	#160
						0o000324,	#520	#162
						0o162704,	#522	#164
						0o000002,	#524	#166
						0o005002,	#526	#168
						0o152502,	#530	#170
						0o060200,	#532	#172
						0o005500,	#534	#174
						0o077405,	#536	#176
						0o020041,	#540	#178
						0o001002,	#542	#180
						0o000137,	#544	#182
						0o001357,	#546	#184  <- LOADER_OFFSET_START_ADDRESS
						0o012701,	#550	#186
						0o100734,	#552	#188
						0o012702,	#554	#190
						0o000006,	#556	#192
						0o104020,	#560	#194
						0o000000 ];	#562	#196
                                            #198
		LOADER_OFFSET_ADDRESS = 22 # Где в загрузчике адрес, с учетом заголовков самого загрузчика (//2)
		LOADER_OFFSET_SIZE = 26 # длина файла
		#var LOADER_START_ADDR_PLACEHOLDER = '001357'; // в ячейку с таким содержимым засовываем адрес запуска файла
		LOADER_OFFSET_START_ADDRESS=184 # Где в загрузчике адрес запуска, с учетом заголовков самого загрузчика (//2)

		def turbo_extend(seq,turbo):
			if turbo==False: return seq
			data=bytearray()
			for i in seq:
				data.append(i)
				data.append(i)
			return data

		def sequence(lenght,turbo=False):
			data=bytearray()
			for i in range(lenght):
				data.extend(turbo_extend(TUNE,turbo))
			data.extend(turbo_extend(AFTER_TUNE,turbo))
			data.extend(turbo_extend(BIT_1,turbo))
			data.extend(turbo_extend(SYNCHRO_LONG,turbo))
			return data

		def write_byte(b,turbo=False):
			data=bytearray()
			d=b
			for i in range(8):
				if (d & 0x01):
					data.extend(turbo_extend(BIT_1,turbo))
				else:
					data.extend(turbo_extend(BIT_0,turbo))
				data.extend(turbo_extend(SYNCHRO_LONG,turbo))
				d=(d>>1)
			return data

		def header(adr,lenght,name,turbo=False):
#			print(name,len(name))
			data=bytearray()
			data.extend(sequence(8,turbo))
			data.extend(write_byte(adr & 0xff,turbo))
			data.extend(write_byte(adr>>8,turbo))
			data.extend(write_byte(lenght & 0xff,turbo))
			data.extend(write_byte(lenght>>8,turbo))
			for i in name: data.extend(write_byte(i,turbo))
			data.extend(sequence(8,turbo))
			return data

		def crc_calc(bin_data,turbo=False):
			crc=0
			data=bytearray()
			for i in range(len(bin_data)-4):
					b=bin_data[i+4]
					crc+=b
					if crc>0xFFFF:  crc-=0xFFFF
			data.extend(write_byte(crc & 0xff,turbo))
			data.extend(write_byte(crc>>8,turbo))
			return data

		def write_data(bin_data,turbo=False):
			data=bytearray()
			for i in range(len(bin_data)-4):
				b=bin_data[i+4]
				data.extend(write_byte(b,turbo))
			return data

		def turbo_seq(count):
			data=bytearray()
			for i in range(count):
				data.extend(TURBO_TUNE)
			data.extend(TURBO_AFTER_TUNE)
			return data

		def turbo_write_byte(b):
			data=bytearray()
			d=b
			for i in range(8):
				if (d & 0x01):
					data.extend(TURBO_BIT_1)
				else:
					data.extend(TURBO_BIT_0)
				d=(d>>1)
			return data

		def turbo_crc_calc(bin_data):
			crc=0
			data=bytearray()
			for i in range(len(bin_data)-4):
					b=bin_data[i+4]
					crc+=b
					if crc>0xFFFF:  crc-=0xFFFF
			data.extend(turbo_write_byte(crc & 0xff))
			data.extend(turbo_write_byte(crc>>8))
			return data

		def turbo_write_data(bin_data):
			data=bytearray()
			for i in range(len(bin_data)-4):
				b=bin_data[i+4]
				data.extend(turbo_write_byte(b))
			return data

		def str_to_koi(s):
			charsList = 'юабцдефгхийклмнопярстужвьызшэщчъЮАБЦДЕФГХИЙКЛМНОПЯРСТУЖВЬЫЗШЭЩЧЪ'
			koi=bytearray()
			d=32
			for c in s:
				if c=='Ё': d=229 #Е
				if c=='ё': d=197 #e
				if ord(c)<32:
					d=32
				else:
					if ord(c)<128:
						d=ord(c)
					else:
						if c in charsList:
							d=192+charsList.index(c)
						else:
							d=32
				koi.append(d)
			if len(koi)<16:
				koi.extend([32]*(16-len(koi)))
			if len(koi)>16:
				koi=koi[:16]
			return koi

		self.wav_data=bytearray()
		if self.name_checkbox.active:
			name=str_to_koi(self.int_name_text.text)
		else:
			name=bytes([32]*16)
		adr=int(self.adr_text.text, base=8)
		lenght=int(self.len_text.text, base=10)
		if self.turbo_checkbox.active:
			pass # turbo
			if lenght & 0x01 ==1:
				lenght+=1
				self.len_text.text=str(lenght)
				self.bindata=bytearray(self.bindata)
				self.bindata.append(0)
			t_adr=LOADER_CODE[0]
			t_ln=LOADER_CODE[1]
			LOADER_CODE[LOADER_OFFSET_ADDRESS//2]=adr
			LOADER_CODE[LOADER_OFFSET_SIZE//2]=lenght + 2 # 2-контрольная сумма
			if adr<0o1000:
				autostart_adr=(self.bindata[4] | self.bindata[5]<<8)
			else:
				autostart_adr=adr
			LOADER_CODE[LOADER_OFFSET_START_ADDRESS//2]=autostart_adr
			self.wav_data.extend(sequence(TUNE_COUNT,True))
			self.wav_data.extend(header(t_adr,t_ln,name,True))
			loader_data=bytearray()
			for w in LOADER_CODE:
				loader_data.append(w & 0xff)
				loader_data.append(w >> 8)
			self.wav_data.extend(write_data(loader_data,True))
			self.wav_data.extend(crc_calc(loader_data,True))
			self.wav_data.extend(turbo_extend(END,True))
			self.wav_data.extend(turbo_seq(TURBO_TUNE_COUNT))
			self.wav_data.extend(turbo_write_data(self.bindata))
			self.wav_data.extend(turbo_crc_calc(self.bindata))
			self.wav_data.extend(turbo_seq(TURBO_TUNE_COUNT_END))

			self.current_chunk=0
			self.total_chunks=len(self.wav_data)//self.chunk_size
			if (len(self.wav_data) % self.chunk_size )>0 : self.total_chunks+=1
			self.pos_percent=0
			self.progress_slider.value=self.pos_percent
			self.status=2
			self.srate=SAMPLE_RATE_TURBO
			self.print(f"Звуковые данные c турбо-загрузчиком сформированы - {len(self.wav_data)} байт, ( {self.total_chunks} блоков по {self.chunk_size})")
		else:
			self.wav_data.extend(sequence(TUNE_COUNT))
			self.wav_data.extend(header(adr,lenght,name))
			self.wav_data.extend(write_data(self.bindata))
			self.wav_data.extend(crc_calc(self.bindata))
			self.wav_data.extend(END)
			self.current_chunk=0
			self.total_chunks=len(self.wav_data)//self.chunk_size
			if (len(self.wav_data) % self.chunk_size )>0 : self.total_chunks+=1
			self.pos_percent=0
			self.progress_slider.value=self.pos_percent
			self.status=2
			self.srate=SAMPLE_RATE_10
			self.print(f"Звуковые данные сформированы - {len(self.wav_data)} байт, ( {self.total_chunks} блоков по {self.chunk_size})")

	@mainthread
	def move_slider(self):
		pos=int((self.current_chunk/self.total_chunks)*100)
		self.pos_percent=pos
		self.progress_slider.value=pos
		if pos==100:
			self.button_start.disabled=False
			self.button_stop.disabled=True

	def play_thread(self):
		if platform=="android":
			AudioManager = autoclass('android.media.AudioManager')
			AudioTrack = autoclass('android.media.AudioTrack')
			AudioFormat = autoclass('android.media.AudioFormat')
			MediaPlayer = autoclass('android.media.MediaPlayer')
			Context = autoclass('android.content.Context')
			PythonActivity = autoclass('org.kivy.android.PythonActivity')

			#BUFFER_SIZE = AudioTrack.getMinBufferSize(   self.srate,     AudioFormat.CHANNEL_OUT_MONO,     AudioFormat.ENCODING_PCM_8BIT )
			#if BUFFER_SIZE < self.chunk_size: BUFFER_SIZE=self.chunk_size

			track = AudioTrack(
								AudioManager.STREAM_MUSIC,
								self.srate,
								AudioFormat.CHANNEL_OUT_MONO,
								AudioFormat.ENCODING_PCM_8BIT,
								self.chunk_size,
								AudioTrack.MODE_STREAM
								)
			track.play()
			while(self.status==3):
				if self.current_chunk<self.total_chunks-1:
					chunk=self.wav_data[self.current_chunk*self.chunk_size:(self.current_chunk+1)*self.chunk_size]
				else:
					chunk=self.wav_data[self.current_chunk*self.chunk_size:]
					chunk.extend([0]*(self.chunk_size-len(chunk)))
					self.status=2
				self.current_chunk+=1
#				print(self.current_chunk, self.total_chunks,self.chunk_size)
				track.write(chunk, 0, self.chunk_size)
				self.move_slider()
				time.sleep(0.01)
			track.write(bytes([128]*self.chunk_size),0,self.chunk_size)
#			track.flush()
			track.stop()
			track.release()









if __name__ == '__main__':
	if platform!="android":
		Window.size=(600,1000)
	MyApp().run()

