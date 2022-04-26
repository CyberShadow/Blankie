# The Python Xlib package does not implement this extension,
# so declare an implementation here.

from Xlib import X
from Xlib.protocol import rq, structs

extname = 'MIT-SCREEN-SAVER'

# Event members
NotifyMask = 1
CycleMask = 2

# Notify state
StateOff = 0
StateOn = 1
StateCycle = 2

# Notify kind
KindBlanked = 0
KindInternal = 1
KindExternal = 2

class QueryVersion(rq.ReplyRequest):
    _request = rq.Struct(
        rq.Card8('opcode'),
        rq.Opcode(0),
        rq.RequestLength(),
        rq.Card8('major_version'),
        rq.Card8('minor_version'),
        rq.Pad(2),
        )

    _reply = rq.Struct(
            rq.ReplyCode(),
            rq.Pad(1),
            rq.Card16('sequence_number'),
            rq.ReplyLength(),
            rq.Card8('major_version'),
            rq.Card8('minor_version'),
            rq.Pad(22),
            )

def query_version(self):
    return QueryVersion(display=self.display,
                        opcode=self.display.get_extension_major(extname),
                        major_version=1,
                        minor_version=0)


class QueryInfo(rq.ReplyRequest):
    _request = rq.Struct(
        rq.Card8('opcode'),
        rq.Opcode(1),
        rq.RequestLength(),
        rq.Drawable('drawable'),
        )

    _reply = rq.Struct(
            rq.ReplyCode(),
            rq.Card8('state'),
            rq.Card16('sequence_number'),
            rq.ReplyLength(),
            rq.Window('saver_window'),
            rq.Card32('til_or_since'),
            rq.Card32('idle'),
            rq.Card32('event_mask'), # rq.Set('event_mask', 4, (NotifyMask, CycleMask)),
            rq.Card8('kind'),
            rq.Pad(10),
            )

def query_info(self):
    return QueryInfo(display=self.display,
                     opcode=self.display.get_extension_major(extname),
                     drawable=self,
                     )


class SelectInput(rq.Request):
    _request = rq.Struct(
        rq.Card8('opcode'),
        rq.Opcode(2),
        rq.RequestLength(),
        rq.Drawable('drawable'),
        rq.Card32('event_mask'), # rq.Set('event_mask', 4, (NotifyMask, CycleMask)),
        )

def select_input(self, mask):
    return SelectInput(display=self.display,
                       opcode=self.display.get_extension_major(extname),
                       drawable=self,
                       event_mask=mask,
                       )


class SetAttributes(rq.Request):
    _request = rq.Struct(
        rq.Card8('opcode'),
        rq.Opcode(3),
        rq.RequestLength(),
        rq.Drawable('drawable'),
        rq.Int16('x'),
        rq.Int16('y'),
        rq.Card16('width'),
        rq.Card16('height'),
        rq.Card16('border_width'),
        rq.Set('window_class', 1, (X.CopyFromParent, X.InputOutput, X.InputOnly)),
        rq.Card8('depth'),
        rq.Card32('visual'),
        structs.WindowValues('attrs'),
        )

def set_attributes(self, x, y, width, height, border_width,
                   window_class = X.CopyFromParent,
                   depth = X.CopyFromParent,
                   visual = X.CopyFromParent,
                   onerror = None,
                   **keys):
    return SetAttributes(display=self.display,
                         onerror = onerror,
                         opcode=self.display.get_extension_major(extname),
                         drawable=self,
                         x = x,
                         y = y,
                         width = width,
                         height = height,
                         border_width = border_width,
                         window_class = window_class,
                         depth = depth,
                         visual = visual,
                         attrs = keys)


class UnsetAttributes(rq.Request):
    _request = rq.Struct(
        rq.Card8('opcode'),
        rq.Opcode(4),
        rq.RequestLength(),
        rq.Drawable('drawable'),
        )

def unset_attributes(self, onerror = None):
    return UnsetAttributes(display=self.display,
                           onerror = onerror,
                           opcode=self.display.get_extension_major(extname),
                           drawable=self)


class Notify(rq.Event):
    _code = None
    _fields = rq.Struct(
        rq.Card8('type'),
        rq.Set('state', 1, (StateOff, StateOn, StateCycle)),
        rq.Card16('sequence_number'),
        rq.Card32('timestamp'),
        rq.Window('root'),
        rq.Window('window'),
        rq.Set('kind', 1, (KindBlanked, KindInternal, KindExternal)),
        rq.Bool('forced'),
        rq.Pad(14),
        )

def init(disp, info):
    disp.extension_add_method('display', 'screensaver_query_version', query_version)
    disp.extension_add_method('drawable', 'screensaver_query_info', query_info)
    disp.extension_add_method('drawable', 'screensaver_select_input', select_input)
    disp.extension_add_method('drawable', 'screensaver_set_attributes', set_attributes)
    disp.extension_add_method('drawable', 'screensaver_unset_attributes', unset_attributes)

    disp.extension_add_event(info.first_event + 0, Notify)

# Mimic Display.__init__ loader for Xlib.ext modules
def load(disp):    
    info = disp.query_extension(extname)
    disp.display.set_extension_major(extname, info.major_opcode)
    init(disp, info)
    disp.extensions.append(extname)

    for class_name, dictionary in disp.class_extension_dicts.items():
        origcls = disp.display.resource_classes[class_name]
        disp.display.resource_classes[class_name] = type(origcls.__name__,
                                                         (origcls,),
                                                         dictionary)

    for screen in disp.display.info.roots:
        screen.root = disp.display.resource_classes['window'](disp.display, screen.root.id)
        screen.default_colormap = disp.display.resource_classes['colormap'](disp.display, screen.default_colormap.id)
