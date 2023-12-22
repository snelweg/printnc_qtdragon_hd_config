#!/usr/bin/env python3
#MIT License

# Copyright (c) 2023 Kenneth Thompson, https://github.com/KennethThompson

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from enum import StrEnum
from os import path
import debugpy
import linuxcnc
import sys
import hal


# 5678 is the default attach port in the VS Code debug configurations. Unless a host and port are specified, host defaults to 127.0.0.1
debugpy.listen(('0.0.0.0',5678))
#print("Waiting for debugger attach")
#debugpy.wait_for_client()
#debugpy.breakpoint()
#print('break on this line')

# Set up logging
from qtvcp import logger
from qtvcp.core import Info, Status, Qhal

from PyQt5 import QtGui

log = logger.getLogger(__name__)

INFO = Info()
STATUS = Status()
QHAL = Qhal()

# Set the log level for this module
log.setLevel(logger.DEBUG) # One of DEBUG, INFO, WARNING, ERROR, CRITICAL

key_index = 0
comp_input_index = 1
default_value = 2

class ToolEntry():
    def __init__(self, line:str) -> None:
        self.params, self.comment = line.split(';')
        self.params = self.params.split()
        self.id = self.params[0]
        self.pocket = self.params[1]
        
'''
    ToolTableReader bypasses a bug in LinuxCNC that prevents tool pockets from being identified.
'''
class ToolTableReader():
    def __init__(self, tooldb:str) -> None:
        self.tools = []
        self.tooldbpath = tooldb
        self.load_tool_db()
    
    def load_tool_db(self):
        self.tools.clear()
        file = open(self.tooldbpath, 'r')
        lns = file.readlines()
        for line in lns:
            self.tools.append(ToolEntry(line))
    
    def get_tool_pocket(self, toolid:int) -> int:
        for tool in self.tools:
            if tool.id == f'T{str(toolid)}':
                return int(tool.pocket[1:])
        return -1
      
class AtcHalPin(StrEnum):
    SAFE_Z = 'safe_z'
    Z_IR_ENGAGE = 'z_ir_engage'
    NUM_POCKETS = 'num_pockets'
    POCKET_OFFSET = 'pocket_offset'
    FIRST_POCKET_X = 'first_pocket_x'
    FIRST_POCKET_Y = 'first_pocket_y'
    ENGAGE_Z =  'engage_z'
    ALIGN_AXIS = 'align_axis'
    ALIGN_DIR = 'align_dir'
    IR_HAL_DPIN = 'ir_hal_dpin'
    COVER_HAL_DPIN = 'cover_hal_dpin'
    ENGAGE_FEED_RATE = 'engage_feed_rate'
    DROP_RATE = 'drop_feed_rate'
    PICKUP_RATE = 'pickup_feed_rate'
    SPINDLE_SPEED = 'spindle_speed'
    X_MANUAL_CHANGE_POS = 'x_manual_change_pos'
    Y_MANUAL_CHANGE_POS = 'y_manual_change_pos'
    CURRENT_TOOL_POCKET = 'current_tool_pocket'
    IR_ENABLED = 'ir_enabled'
    COVER_ENABLED = 'cover_enabled'
    DUST_COVER_STATE = 'dust_cover_state'
    def __str__(self) -> str:
        return self.value

class ConfigElement(StrEnum):
    ATC_SECTION = 'RAPID_ATC'
    NUM_POCKETS = 'num_pockets'
    POCKET_OFFSET = 'pocket_offset'
    FIRST_POCKET_X = 'first_pocket_x'
    FIRST_POCKET_Y = 'first_pocket_y'
    Z_ENGAGE = 'z_engage'
    Z_IR_ENGAGE = 'z_ir_engage'
    COVER_HAL_DPIN = 'cover_hal_dpin'
    IR_HAL_DPIN = 'ir_hal_dpin'
    Z_SAFE_CLEARANCE = 'z_safe_clearance'
    X_MANUAL_CHANGE_POS = 'x_manual_change_pos'
    Y_MANUAL_CHANGE_POS = 'y_manual_change_pos'
    ALIGN_AXIS = 'align_axis'
    ALIGN_DIR = 'align_dir'
    ENGAGE_FEED_RATE = 'engage_feed_rate'
    PICKUP_RATE = 'pickup_rate'
    DROP_RATE = 'drop_rate'
    SPINDLE_SPEED = 'spindle_speed'
    IR_ENABLED = 'ir_enabled'
    COVER_ENABLED = 'cover_enabled'
    
    def __str__(self) -> str:
        return self.value
    
    

###################################
# **** HANDLER CLASS SECTION **** #
###################################

class HandlerClass:
    #r = rapidChangeBase()

    ########################
    # **** INITIALIZE **** #
    ########################
    # widgets allows access to  widgets from the QtVCP files
    # at this point the widgets and hal pins are not instantiated
    def __init__(self, halcomp,widgets,paths):
        self.hal = halcomp
        self.w = widgets
        self.PATHS = paths
        self.iniFile = INFO.INI
        self.machineName = self.iniFile.find('EMC', 'MACHINE')
        self.c = hal.component('rapid_atc')
        self.configPath = paths.CONFIGPATH
        self.toolTablePath = path.join(self.configPath, 'tool.tbl')
        self.tooldb = ToolTableReader(tooldb=self.toolTablePath)
        self.currentTool = 0
        self.currentToolPocketNo = 0

    
    def onTextChanged(self, s:str):
        print(f'Text Changed: {s}')

    ##########################################
    # SPECIAL FUNCTIONS SECTION              #
    ##########################################

    # at this point:
    # the widgets are instantiated.
    # the HAL pins are built but HAL is not set ready
    # This is where you make HAL pins or initialize state of widgets etc
    def initialized__(self):
        log.debug('INIT qtvcp handler')
        if not self.w.MAIN.PREFS_:
            err = "CRITICAL - no preference file found, enable preferences in screenoptions widget"
            log.debug(err)
            print(err)
            return

        if self.w.MAIN.PREFS_:
            '''
            [ATC]
            NUM_POCKETS = 4
            FIRST_POCKET_X = 476.8
            FIRST_POCKET_Y = 1
            FIRST_POCKET_Z = 4.3
            DELTA_X = 52
            DELTA_Y = 0
            OFF_HEIGHT_Z = 35
            WAIT_SPINDLE = 2
            CHANGE_X = 200
            CHANGE_Y = 1
            CHANGE_Z = 167
            SPINDLE_SPEED = 800
            UNLOAD_ZSPEED = 2000
            LOAD_ZSPEED = 870
            '''
            
            # PIN definitions
            self.c.newpin(AtcHalPin.SAFE_Z, hal.HAL_FLOAT, hal.HAL_IN)
            self.c.newpin(AtcHalPin.Z_IR_ENGAGE, hal.HAL_FLOAT, hal.HAL_IN)
            self.c.newpin(AtcHalPin.NUM_POCKETS, hal.HAL_S32, hal.HAL_IN)
            self.c.newpin(AtcHalPin.POCKET_OFFSET, hal.HAL_FLOAT, hal.HAL_IN)
            self.c.newpin(AtcHalPin.FIRST_POCKET_X, hal.HAL_FLOAT, hal.HAL_IN)
            self.c.newpin(AtcHalPin.FIRST_POCKET_Y, hal.HAL_FLOAT, hal.HAL_IN)
            self.c.newpin(AtcHalPin.X_MANUAL_CHANGE_POS, hal.HAL_FLOAT, hal.HAL_IN)
            self.c.newpin(AtcHalPin.Y_MANUAL_CHANGE_POS, hal.HAL_FLOAT, hal.HAL_IN)
            self.c.newpin(AtcHalPin.ENGAGE_Z, hal.HAL_FLOAT, hal.HAL_IN)
            self.c.newpin(AtcHalPin.ALIGN_AXIS, hal.HAL_BIT, hal.HAL_IN)
            self.c.newpin(AtcHalPin.ALIGN_DIR, hal.HAL_S32, hal.HAL_IN)
            self.c.newpin(AtcHalPin.ENGAGE_FEED_RATE, hal.HAL_S32, hal.HAL_IN)
            self.c.newpin(AtcHalPin.DROP_RATE, hal.HAL_S32, hal.HAL_IN)
            self.c.newpin(AtcHalPin.PICKUP_RATE, hal.HAL_S32, hal.HAL_IN)
            self.c.newpin(AtcHalPin.SPINDLE_SPEED, hal.HAL_S32, hal.HAL_IN)
            self.c.newpin(AtcHalPin.CURRENT_TOOL_POCKET, hal.HAL_S32, hal.HAL_IN)
            self.c.newpin(AtcHalPin.IR_ENABLED, hal.HAL_BIT, hal.HAL_IN)
            self.c.newpin(AtcHalPin.COVER_ENABLED, hal.HAL_BIT, hal.HAL_IN)
            self.c.newpin(AtcHalPin.IR_HAL_DPIN, hal.HAL_S32, hal.HAL_IN)
            self.c.newpin(AtcHalPin.COVER_HAL_DPIN, hal.HAL_S32, hal.HAL_OUT)
            self.c.newpin(AtcHalPin.DUST_COVER_STATE, hal.HAL_BIT, hal.HAL_OUT)
            # Wire periodic update function
            STATUS.connect('periodic', lambda w: self.updatePeriodic())
            
            # UI elements
            self.w.pbSetXYPocketOne.clicked.connect( lambda: self.setXYPocketOne() )

            self.w.pbSetZEngage.clicked.connect(lambda: self.setZEngage() )

            self.w.pbSetZIREngage.clicked.connect(lambda: self.setZIREngage() )

            self.w.btnAdd.clicked.connect(lambda: (self.w.tooloffsetview.add_tool(),\
                                            self.w.tooloffsetview.repaint()))
            self.w.btnDelete.clicked.connect(lambda:(self.w.tooloffsetview.delete_tools(),\
                                                self.w.tooloffsetview.repaint()))
            self.w.pbSafeZ.clicked.connect(
                lambda: self.executeProgram('o<_go_to_pos> call')
            )
            self.w.pbToolChangeTest.clicked.connect(
                lambda: self.executeProgram('o<_tool_change> call [5]')
            )
            self.w.pbDropToolTest.clicked.connect(
                lambda: self.executeProgram(f'o<_drop_tool> call [{self.currentToolPocketNo}]')
            )

            self.w.btnIREnabled.clicked.connect(
                lambda: ( self.setIREnabled(not self.w.btnIREnabled.isChecked()))
            )

            self.w.btnCoverEnabled.clicked.connect(
                lambda: ( self.setCoverEnabled(not self.w.btnCoverEnabled.isChecked()))
            )

            self.w.btnDustCoverToggle.clicked.connect(
                lambda: self.toggleDustCover()
            )


            self.w.btnM61.clicked.connect( lambda: self.loadToolViaM61() )
            
            '''
                Removed columns from tooloffsetview that are extraneous/unused by ATC Logic
            '''
            # https://linuxcnc.org/docs/2.9/html/gui/qtvcp-widgets.html#sub:qtvcp:widgets:tooloffsetview
           # self.w.tooloffsetview.hideColumn(2) 
            self.w.tooloffsetview.hideColumn(3)
            self.w.tooloffsetview.hideColumn(4)
            self.w.tooloffsetview.hideColumn(5)
            self.w.tooloffsetview.hideColumn(6)
            self.w.tooloffsetview.hideColumn(7)
            self.w.tooloffsetview.hideColumn(8)
            self.w.tooloffsetview.hideColumn(9)
            self.w.tooloffsetview.hideColumn(10)
            self.w.tooloffsetview.hideColumn(11)

            '''
                num_pockets : Number of tool pocketsi available for tool changing
            '''
            num_pockets = self.w.MAIN.PREFS_.getpref(ConfigElement.NUM_POCKETS, 4, int, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.NUM_POCKETS} = {num_pockets}')
            self.c[AtcHalPin.NUM_POCKETS] = int(num_pockets)
            self.numPocketInput = self.w.leNoPockets
            self.numPocketInput.setText(str(num_pockets))
            self.numPocketInput.editingFinished.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.NUM_POCKETS, int(self.numPocketInput.text()), int, ConfigElement.ATC_SECTION),
                        log.debug(f'SETTING {ConfigElement.NUM_POCKETS} = {self.numPocketInput.text()} in preferences'),
                         self.setPinValue( pinName = AtcHalPin.NUM_POCKETS, pinVal = int(self.numPocketInput.text()))))
            
            '''
                pocket_offset : Offset between tool pockets
            '''
            pocket_offset = self.w.MAIN.PREFS_.getpref(ConfigElement.POCKET_OFFSET, "52.1", str, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.POCKET_OFFSET} = {pocket_offset}')
            self.c[AtcHalPin.POCKET_OFFSET] = float(pocket_offset)
            self.pocketOffsetInput = self.w.lePocketOffset
            
            self.pocketOffsetInput.setValidator(
            QtGui.QDoubleValidator(
                0.0, # bottom
                5000, # top
                3, # decimals 
                notation=QtGui.QDoubleValidator.StandardNotation
            ))
            self.pocketOffsetInput.setText(str(pocket_offset))
            self.pocketOffsetInput.editingFinished.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.POCKET_OFFSET, self.pocketOffsetInput.text(), str, ConfigElement.ATC_SECTION),
                         log.debug(f'SETTING {ConfigElement.POCKET_OFFSET} = {self.pocketOffsetInput.text()} in preferences'),
                         self.setPinValue( pinName = AtcHalPin.POCKET_OFFSET, pinVal = float(self.pocketOffsetInput.text()))
                        )
                )
            
            '''
                first_pocket_x : X pos of first pocket
            '''
            first_pocket_x = self.w.MAIN.PREFS_.getpref(ConfigElement.FIRST_POCKET_X, "0", str, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.FIRST_POCKET_X} = {first_pocket_x}')
            self.c[AtcHalPin.FIRST_POCKET_X] = float(first_pocket_x)
            self.firstPocketXInput = self.w.leLocPocketOneX
            self.firstPocketXInput.setValidator(
            QtGui.QDoubleValidator(
                -5000, # bottom
                5000, # top
                3, # decimals 
                notation=QtGui.QDoubleValidator.StandardNotation
            ))
            self.firstPocketXInput.setText(str(first_pocket_x))
            self.firstPocketXInput.editingFinished.connect(
                    lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.FIRST_POCKET_X, self.firstPocketXInput.text(), str, ConfigElement.ATC_SECTION),
                    log.debug(f'SETTING {ConfigElement.FIRST_POCKET_X} = {self.firstPocketXInput.text()} in preferences'),
                    self.setPinValue( pinName = AtcHalPin.FIRST_POCKET_X, pinVal = float(self.firstPocketXInput.text()))))
            '''
                first_pocket_y : Y pos of first pocket
            '''
            first_pocket_y = self.w.MAIN.PREFS_.getpref(ConfigElement.FIRST_POCKET_Y, "0", str, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.FIRST_POCKET_Y} = {first_pocket_y}')
            self.c[AtcHalPin.FIRST_POCKET_Y] = float(first_pocket_y)
            self.firstPocketYInput = self.w.leLocPocketOneY
            self.firstPocketYInput.setValidator(
            QtGui.QDoubleValidator(
                -5000, # bottom
                5000, # top
                3, # decimals 
                notation=QtGui.QDoubleValidator.StandardNotation
            ))
            self.firstPocketYInput.setText(str(first_pocket_y))
            self.firstPocketYInput.editingFinished.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.FIRST_POCKET_Y, self.firstPocketYInput.text(), str, ConfigElement.ATC_SECTION),
                log.debug(f'SETTING {ConfigElement.FIRST_POCKET_Y} = {self.firstPocketYInput.text()} in preferences'),
                self.setPinValue( pinName = AtcHalPin.FIRST_POCKET_Y, pinVal = float(self.firstPocketYInput.text()))))
            '''
                z_engage : Z engage position
            '''
            z_engage = self.w.MAIN.PREFS_.getpref(ConfigElement.Z_ENGAGE, "0", str, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.Z_ENGAGE} = {z_engage}')
            self.c[AtcHalPin.ENGAGE_Z] = float(z_engage)
            self.zEngageInput = self.w.leLocZEngage
            self.zEngageInput.setValidator(
            QtGui.QDoubleValidator(
                -5000, # bottom
                5000, # top
                3, # decimals 
                notation=QtGui.QDoubleValidator.StandardNotation
            ))
            self.zEngageInput.setText(str(z_engage))
            self.zEngageInput.editingFinished.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.Z_ENGAGE, self.zEngageInput.text(), str, ConfigElement.ATC_SECTION),
                log.debug(f'SETTING {ConfigElement.Z_ENGAGE} = {self.zEngageInput.text()} in preferences'),
                self.setPinValue( pinName = AtcHalPin.ENGAGE_Z, pinVal = float(self.zEngageInput.text()))))
            '''
                z_ir_engage : Z IR engage position
            '''
            z_ir_engage = self.w.MAIN.PREFS_.getpref(ConfigElement.Z_IR_ENGAGE, "0", str, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.Z_IR_ENGAGE} = {z_ir_engage}')
            self.c[AtcHalPin.Z_IR_ENGAGE] = float(z_ir_engage)
            self.zEngageIRInput = self.w.leLocZIREngage
            self.zEngageIRInput.setValidator(
            QtGui.QDoubleValidator(
                -5000, # bottom
                5000, # top
                3, # decimals 
                notation=QtGui.QDoubleValidator.StandardNotation
            ))
            self.zEngageIRInput.setText(str(z_ir_engage))
            self.zEngageIRInput.editingFinished.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.Z_IR_ENGAGE, self.zEngageIRInput.text(), str, ConfigElement.ATC_SECTION),
                log.debug(f'SETTING {ConfigElement.Z_IR_ENGAGE} = {self.zEngageIRInput.text()} in preferences'),
                self.setPinValue( pinName = AtcHalPin.ENGAGE_IR_Z, pinVal = float(self.zEngageIRInput.text()))))
            '''
                z_safe_clearance 
            '''
            z_safe_clearance = self.w.MAIN.PREFS_.getpref(ConfigElement.Z_SAFE_CLEARANCE, "0", str, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.Z_SAFE_CLEARANCE} = {z_safe_clearance}')
            self.c[AtcHalPin.SAFE_Z] = float(z_safe_clearance)
            self.zSafeClearanceInput = self.w.leZSafeClearance
            self.zSafeClearanceInput.setValidator(
            QtGui.QDoubleValidator(
                -5000, # bottom
                5000, # top
                3, # decimals 
                notation=QtGui.QDoubleValidator.StandardNotation
            ))
            self.zSafeClearanceInput.setText(z_safe_clearance)
            self.zSafeClearanceInput.editingFinished.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.Z_SAFE_CLEARANCE, self.zSafeClearanceInput.text(), str, ConfigElement.ATC_SECTION),
                log.debug(f'SETTING {ConfigElement.Z_SAFE_CLEARANCE} = {self.zSafeClearanceInput.text()} in preferences'),
                self.setPinValue( pinName = AtcHalPin.SAFE_Z, pinVal = float(self.zSafeClearanceInput.text()))))
            '''
                cover_hal_dpin 
            '''
            cover_hal_dpin = self.w.MAIN.PREFS_.getpref(ConfigElement.COVER_HAL_DPIN, 2, int, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.COVER_HAL_DPIN} = {cover_hal_dpin}')
            self.c[AtcHalPin.COVER_HAL_DPIN] = int(cover_hal_dpin)
            self.coverDPinInput = self.w.leCoverDPinInput
            self.coverDPinInput.setText(str(cover_hal_dpin))
            self.coverDPinInput.editingFinished.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.COVER_HAL_DPIN, self.coverDPinInput.text(), str, ConfigElement.ATC_SECTION),
                log.debug(f'SETTING {ConfigElement.COVER_HAL_DPIN} = {self.coverDPinInput.text()} in preferences'),
                self.setPinValue( pinName = AtcHalPin.COVER_HAL_DPIN, pinVal = int(self.coverDPinInput.text()))))
            '''
                ir_hal_dpin 
            '''
            ir_hal_dpin = self.w.MAIN.PREFS_.getpref(ConfigElement.IR_HAL_DPIN, 3, int, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.IR_HAL_DPIN} = {ir_hal_dpin}')
            self.c[AtcHalPin.IR_HAL_DPIN] = int(ir_hal_dpin)
            self.irDPinInput = self.w.leIRDPinInput
            self.coverDPinInput.setText(str(ir_hal_dpin))
            self.coverDPinInput.editingFinished.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.IR_HAL_DPIN, self.coverDPinInput.text(), str, ConfigElement.ATC_SECTION),
                log.debug(f'SETTING {ConfigElement.IR_HAL_DPIN} = {self.coverDPinInput.text()} in preferences'),
                self.setPinValue( pinName = AtcHalPin.IR_HAL_DPIN, pinVal = int(self.coverDPinInput.text()))))
            '''
                x_manual_change_pos 
            '''
            x_manual_change_pos = self.w.MAIN.PREFS_.getpref(ConfigElement.X_MANUAL_CHANGE_POS, "0", str, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.X_MANUAL_CHANGE_POS} = {x_manual_change_pos}')
            self.c[AtcHalPin.X_MANUAL_CHANGE_POS] = float(x_manual_change_pos)
            self.xManualChangePosInput = self.w.leXManualChangePos
            self.xManualChangePosInput.setValidator(
            QtGui.QDoubleValidator(
                -5000, # bottom
                5000, # top
                3, # decimals 
                notation=QtGui.QDoubleValidator.StandardNotation
            ))
            self.xManualChangePosInput.setText(str(x_manual_change_pos))
            self.xManualChangePosInput.editingFinished.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.X_MANUAL_CHANGE_POS, self.xManualChangePosInput.text(), str, ConfigElement.ATC_SECTION),
                log.debug(f'SETTING {ConfigElement.X_MANUAL_CHANGE_POS} = {self.xManualChangePosInput.text()} in preferences'),
                self.setPinValue( pinName = AtcHalPin.X_MANUAL_CHANGE_POS, pinVal = float(self.xManualChangePosInput.text())
                )
            ))
            '''
                y_manual_change_pos 
            '''
            y_manual_change_pos = self.w.MAIN.PREFS_.getpref(ConfigElement.Y_MANUAL_CHANGE_POS, "0", str, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.Y_MANUAL_CHANGE_POS} = {y_manual_change_pos}')
            self.c[AtcHalPin.Y_MANUAL_CHANGE_POS] = float(y_manual_change_pos)
            self.yManualChangePosInput = self.w.leYManualChangePos
            self.yManualChangePosInput.setValidator(
            QtGui.QDoubleValidator(
                -5000, # bottom
                5000, # top
                3, # decimals 
                notation=QtGui.QDoubleValidator.StandardNotation
            ))
            self.yManualChangePosInput.setText(str(y_manual_change_pos))
            self.yManualChangePosInput.editingFinished.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.Y_MANUAL_CHANGE_POS, self.yManualChangePosInput.text(), int, ConfigElement.ATC_SECTION),
                log.debug(f'SETTING {ConfigElement.Y_MANUAL_CHANGE_POS} = {self.yManualChangePosInput.text()} in preferences'),
                self.setPinValue( pinName = AtcHalPin.Y_MANUAL_CHANGE_POS, pinVal = float(self.yManualChangePosInput.text())
                )
            ))
            '''
                align_axis 
            '''
            align_axis = self.w.MAIN.PREFS_.getpref(ConfigElement.ALIGN_AXIS, 'X', str, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.ALIGN_AXIS} = {align_axis}')
            if align_axis.lower() == 'x':
                self.w.pbXAxis.setChecked(True)
                self.w.pbYAxis.setChecked(False)
                self.c[AtcHalPin.ALIGN_AXIS] = 0
            else:
                self.w.pbYAxis.setChecked(True)
                self.w.pbXAxis.setChecked(False)
                self.c[AtcHalPin.ALIGN_AXIS] = 0

            self.w.pbXAxis.clicked.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.ALIGN_AXIS, 'X', str, ConfigElement.ATC_SECTION),
                    self.w.pbXAxis.setEnabled(False),
                    self.w.pbYAxis.setEnabled(True),
                    self.w.pbYAxis.setChecked(False),
                    self.setPinValue( pinName = AtcHalPin.ALIGN_AXIS, pinVal = 0),
                    log.debug(f'SETTING {ConfigElement.ALIGN_AXIS} = X in preferences'))
                )
            self.w.pbYAxis.clicked.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.ALIGN_AXIS, 'Y', str, ConfigElement.ATC_SECTION),
                    self.w.pbYAxis.setEnabled(False),
                    self.w.pbXAxis.setEnabled(True), 
                    self.w.pbXAxis.setChecked(False),
                    self.setPinValue( pinName = AtcHalPin.ALIGN_AXIS, pinVal = 1),
                    log.debug(f'SETTING {ConfigElement.ALIGN_AXIS} = Y in preferences'))
                )
            '''
                align_dir
            '''
            align_dir = self.w.MAIN.PREFS_.getpref(ConfigElement.ALIGN_DIR, 'POS', str, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.ALIGN_DIR} = {align_dir}')
            if align_dir.lower() == 'pos':
                self.w.pbDirectionPos.setChecked(True)
                self.w.pbDirectionNeg.setChecked(False)
                self.setPinValue( pinName = AtcHalPin.ALIGN_DIR, pinVal = 1)
            else:
                self.w.pbDirectionNeg.setChecked(True)
                self.w.pbDirectionPos.setChecked(False)
                self.setPinValue( pinName = AtcHalPin.ALIGN_DIR, pinVal = -1)
            
            self.w.pbDirectionPos.clicked.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.ALIGN_DIR, 'POS', str, ConfigElement.ATC_SECTION),
                    self.w.pbDirectionPos.setEnabled(False),
                    self.w.pbDirectionNeg.setEnabled(True),
                    self.w.pbDirectionNeg.setChecked(False),
                    self.setPinValue( pinName = AtcHalPin.ALIGN_DIR, pinVal = 1),
                    log.debug(f'SETTING {ConfigElement.ALIGN_DIR} = POS in preferences'))
                )
            self.w.pbDirectionNeg.clicked.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.ALIGN_DIR, 'NEG', str, ConfigElement.ATC_SECTION),
                    self.w.pbDirectionNeg.setEnabled(False),
                    self.w.pbDirectionPos.setEnabled(True), 
                    self.w.pbDirectionPos.setChecked(False),
                    self.setPinValue( pinName = AtcHalPin.ALIGN_DIR, pinVal = -1),
                    log.debug(f'SETTING {ConfigElement.ALIGN_DIR} = NEG in preferences'))
                )
            '''
                engage_feed_rate 
            '''
            engage_feed_rate = self.w.MAIN.PREFS_.getpref(ConfigElement.ENGAGE_FEED_RATE, 200, int, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.ENGAGE_FEED_RATE} = {engage_feed_rate}')
            self.engageFeedRateInput = self.w.leSFEngageFeedRate
            self.engageFeedRateInput.setText(str(engage_feed_rate))
            self.engageFeedRateInput.editingFinished.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.ENGAGE_FEED_RATE, int(self.engageFeedRateInput.text()), int, ConfigElement.ATC_SECTION),
                self.setPinValue( pinName = AtcHalPin.ENGAGE_FEED_RATE, pinVal = int(self.engageFeedRateInput.text())),
                log.debug(f'SETTING {ConfigElement.ENGAGE_FEED_RATE} = {self.engageFeedRateInput.text()} in preferences'))
                )
            
            '''
                pickup_rate 
            '''
            pickup_rate = self.w.MAIN.PREFS_.getpref(ConfigElement.PICKUP_RATE, 200, int, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.PICKUP_RATE} = {pickup_rate}')
            self.pickupRateInput = self.w.leSFPickUpRate
            self.pickupRateInput.setText(str(pickup_rate))
            self.pickupRateInput.editingFinished.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.PICKUP_RATE, int(self.pickupRateInput.text()), int, ConfigElement.ATC_SECTION),
                self.setPinValue( pinName = AtcHalPin.PICKUP_RATE, pinVal = int(self.pickupRateInput.text())),
                log.debug(f'SETTING {ConfigElement.PICKUP_RATE} = {self.pickupRateInput.text()} in preferences'))
                )
            '''
                drop_rate 
            '''
            drop_rate = self.w.MAIN.PREFS_.getpref(ConfigElement.DROP_RATE, 200, int, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.DROP_RATE} = {drop_rate}')
            self.dropRateInput = self.w.leSFDropRate
            self.dropRateInput.setText(str(drop_rate))
            self.dropRateInput.editingFinished.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.DROP_RATE, int(self.dropRateInput.text()), int, ConfigElement.ATC_SECTION),
                self.setPinValue( pinName = AtcHalPin.DROP_RATE, pinVal = int(self.dropRateInput.text())),
                log.debug(f'SETTING {ConfigElement.DROP_RATE} = {self.dropRateInput.text()} in preferences'))
                )
            '''
                spindle_speed 
            '''
            spindle_speed = self.w.MAIN.PREFS_.getpref(ConfigElement.SPINDLE_SPEED, 800, int, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.SPINDLE_SPEED} = {spindle_speed}')
            self.spindleSpeedInput = self.w.leToolIRSpindleSpeed
            self.spindleSpeedInput.setText(str(spindle_speed))
            self.spindleSpeedInput.editingFinished.connect(
                lambda: (self.w.MAIN.PREFS_.putpref(ConfigElement.SPINDLE_SPEED, int(self.spindleSpeedInput.text()), int, ConfigElement.ATC_SECTION),
                self.setPinValue( pinName = AtcHalPin.SPINDLE_SPEED, pinVal = int(self.spindleSpeedInput.text())),
                log.debug(f'SETTING {ConfigElement.SPINDLE_SPEED} = {self.spindleSpeedInput.text()} in preferences'))
                )
            '''
                ir_enabled
            '''
            ir_enabled = self.w.MAIN.PREFS_.getpref(ConfigElement.IR_ENABLED, True, bool, ConfigElement.ATC_SECTION)
            log.debug(f'{ConfigElement.IR_ENABLED} = {ir_enabled}')
            self.irEnabledInput = self.w.btnIREnabled
            self.irEnabledInput.setChecked(ir_enabled)
            
            self.c.ready()


    #######################
    # CALLBACKS FROM FORM #
    #######################
    def executeProgram(self, s:str):
        command = linuxcnc.command()
        command.mode(linuxcnc.MODE_MDI)
        command.wait_complete()
        command.mdi(s)
        command.wait_complete()

    def setPinValue(self, pinName:str, pinVal):
        self.c[pinName] = pinVal
        
    def setIREnabled(self, b:bool):
        if b == True:
            self.setPinValue(pinName=AtcHalPin.IR_ENABLED, pinVal=1)
        else:
            self.setPinValue(pinName=AtcHalPin.IR_ENABLED, pinVal=0)
        self.w.MAIN.PREFS_.putpref(ConfigElement.IR_ENABLED, b, bool, ConfigElement.ATC_SECTION)
        self.w.btnIREnabled.setChecked(b)

    def setCoverEnabled(self, b:bool):
        if b == True:
            self.setPinValue(pinName=AtcHalPin.COVER_ENABLED, pinVal=1)
        else:
            self.setPinValue(pinName=AtcHalPin.COVER_ENABLED, pinVal=0)
        self.w.MAIN.PREFS_.putpref(ConfigElement.COVER_ENABLED, b, bool, ConfigElement.ATC_SECTION)
        self.w.btnCoverEnabled.setChecked(b)

    def toggleDustCover(self):
        b = self.c[AtcHalPin.DUST_COVER_STATE]
        if b == 0:
            self.executeProgram('o<_dust_cover_op> call [1]')
        else:
            self.executeProgram('o<_dust_cover_op> call [0]')
        

    
        
    def toggleAllHomed(self, w, data):
        print(f'toggleAllHomed = {data}')
        pass

    def updatePeriodic(self):
        homed = QHAL.getvalue('motion.is-all-homed')
        machine_on = QHAL.getvalue('halui.machine.is-on')
        self.w.gbToolActions.setEnabled((homed & machine_on))
        self.w.gbMacros.setEnabled((homed & machine_on))
        self.w.lblMachineOnNotice.setVisible(not (homed & machine_on))
        
        s = self.getCurrentStat()#linuxcnc.stat()
        s.poll()
        if s.tool_in_spindle == 0:
            self.w.lblToolNo.setText('EMPTY')
            self.currentTool = 0
            self.currentToolPocketNo = 0
            self.w.lblToolPocket.setText('NONE')
        else:
            if s.interp_state == linuxcnc.INTERP_IDLE:
                self.currentTool = s.tool_in_spindle
                self.w.lblToolNo.setText(str(s.tool_in_spindle))
                self.tooldb.load_tool_db() # force a reload to catch any changes
                p = self.getToolPocketByIndex(s.tool_in_spindle)
                self.currentToolPocketNo = p
                self.setPinValue(pinName=AtcHalPin.CURRENT_TOOL_POCKET, pinVal=p)
                self.w.lblToolPocket.setText(str(p))

    '''
        def outputToolTable(self):
        self.executeProgram('o<_current_tool_info> call')
        toolList = self.loadToolViaM61()
        print(f'Tool List = {toolList}')
        s = linuxcnc.stat()
        s.poll()
        # to find the loaded tool information it is in tool table index 0
        if s.tool_table[0].id != 0: # a tool is loaded
            print(s.tool_table[0].zoffset)
        else:
            print("no tool loaded")
    '''

            
    def getToolPocketByIndex(self, index):
        return self.tooldb.get_tool_pocket(toolid=index)
        
            
    def getCurrentStat(self):
        try:
            s = linuxcnc.stat() # create a connection to the status channel
            s.poll() # get current values
            return s
        except linuxcnc.error as detail:
            log.error(f'Error: {detail}')
            sys.exit(1)  

    def loadToolViaM61(self):
        t = self.getSelectedToolFromTable()
        if len(t) > 0:
            self.executeProgram(f'M61 Q{t[0]}')
            self.w.tooloffsetview.repaint()
            cmd = linuxcnc.command()
            cmd.load_tool_table()
        
    def getSelectedToolFromTable(self):
        tool = self.w.tooloffsetview.get_checked_list()
        return tool
    
    def setXYPocketOne(self):
        stat = self.getCurrentStat()
        x_pos = round(stat.position[0], 3)
        y_pos = round(stat.position[1], 3)
        
        self.w.MAIN.PREFS_.putpref(ConfigElement.FIRST_POCKET_Y, str(x_pos), str, ConfigElement.ATC_SECTION)
        self.firstPocketXInput.setText(str(x_pos))
        self.w.MAIN.PREFS_.putpref(ConfigElement.FIRST_POCKET_X, str(y_pos), str, ConfigElement.ATC_SECTION)
        self.firstPocketYInput.setText(str(y_pos))
        
    def setZEngage(self):
        stat = self.getCurrentStat()
        z_pos = round(stat.position[2], 3)
        self.w.MAIN.PREFS_.putpref(ConfigElement.Z_ENGAGE, str(z_pos), str, ConfigElement.ATC_SECTION)
        self.zEngageInput.setText(str(z_pos))

    def setZIREngage(self):
        stat = self.getCurrentStat()
        z_pos = round(stat.position[2], 3)
        self.w.MAIN.PREFS_.putpref(ConfigElement.Z_IR_ENGAGE, str(z_pos), str, ConfigElement.ATC_SECTION)
        self.zEngageIRInput.setText(str(z_pos))

    def isMachineMetric(self) -> bool:
        return INFO.MACHINE_IS_METRIC
    ##############################
    # required class boiler code #
    ##############################
    def closing_cleanup__(self):
        #print('***CLOSE***', self.w.belt_1.isChecked())
        log.debug(f'Calling cleanup for shutdown..')
        self.c.exit() # Call Component's exist function per https://linuxcnc.org/docs/html/hal/halmodule.html
        if self.w.MAIN.PREFS_:
            pass

    def __getitem__(self, item):
        return getattr(self, item) 
    def __setitem__(self, item, value):
        return setattr(self, item, value)

################################
# required handler boiler code #
################################

def get_handlers(halcomp,widgets,paths):
     return [HandlerClass(halcomp,widgets,paths)]
