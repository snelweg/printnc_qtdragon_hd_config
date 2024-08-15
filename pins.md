| heading| ini name| comment|
| -----------------------|--------------------------------|---------------------------|
|TOOLSENSOR|MAXPROBE||
||X|tool sensor position|
||Y||
||Z||
||MAX_PROBE||
|AXIS_X|MAX_LIMIT||
|AXIS_Y|MAX_LIMIT||
|AXIS_Z|MAX_LIMIT||
|ATC|NUMPOCKETS||
||FIRSTPOCKET_X||
||FIRSTPOCKET_Y||
||FIRSTPOCKET_Z||
||DELTA_X||
||DELTA_Y||
||OFF_HEIGHT_Z||
||CHANGEX|manual pick up|
||CHANGEY||
||CHANGEZ||
|ATC_PINS|CLEAN_TS|airblast to clean tool length sensor|

|Purpose pin name| | comment|
| -----------------------|--|---------------------------|
||rapid_atc.num_pockets|||
||gmoccapy.searchvel|||
||gmoccapy.probevel|||
||gmoccapy.probeheight|||
||gmoccapy.blockheight|||
||rapid_atc.num_pockets
||rapid_atc.safe_z|to Safe Z Position|
|pockets|rapid_atc.align_axis
||rapid_atc.first_pocket_x
||rapid_atc.first_pocket_y
||rapid_atc.pocket_offset
|IR|rapid_atc.z_ir_engage|move (back) to IR engage |
||rapid_atc.ir_enabled
||rapid_atc.IR_HAL_DPIN
||rapid_atc.spindle_speed_pickup|Rotate spindle |
||rapid_atc.engage_z
||rapid_atc.pickup_feed_rate|pickup tool from pocket|
|cover|rapid_atc.cover_enabled||






