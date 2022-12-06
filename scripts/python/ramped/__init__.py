from __future__ import annotations

from typing import Optional
import hou
from .window import EditorWindow

ramped_window: Optional[EditorWindow] = None

def is_float_ramp(parms: list[hou.Parm]) -> bool:
    if not parms:
        return False
    parm: hou.Parm = parms[0] 
    parm_template: hou.ParmTemplate = parm.parmTemplate() 
    if parm_template.type() == hou.parmTemplateType.Ramp and parm_template.parmType() == hou.rampParmType.Float:
        return True
    return False


    
def show_ramp_editor(parm: hou.Parm):

    global ramped_window

    if ramped_window is None:

        ramped_window = EditorWindow()
        ramped_window.ui.editor.attach_parm(parm)
        ramped_window.resize(1600, 900)
        ramped_window.show()

    else:

        ramped_window.ui.editor.attach_parm(parm)
        ramped_window.show()
        ramped_window.activateWindow()

    




