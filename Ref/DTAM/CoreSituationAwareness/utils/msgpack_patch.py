"""
Msgpack compatibility patch for older msgpack-rpc-python library

This module patches msgpack.Packer and msgpack.Unpacker to ignore the 'encoding'
parameter which is no longer supported in msgpack >= 1.0.0 but is still used by
msgpack-rpc-python.

Import this module before using msgpackrpc to apply the patches.
"""

import msgpack

# Apply patch only once
if not hasattr(msgpack, '_encoding_patch_applied'):
    _original_packer = msgpack.Packer
    _original_unpacker = msgpack.Unpacker
    
    class PatchedPacker(_original_packer):
        def __init__(self, *args, **kwargs):
            # Remove encoding parameter that's not supported in newer msgpack
            kwargs.pop('encoding', None)
            super().__init__(*args, **kwargs)
    
    class PatchedUnpacker(_original_unpacker):
        def __init__(self, *args, **kwargs):
            # Remove encoding parameter that's not supported in newer msgpack
            kwargs.pop('encoding', None)
            super().__init__(*args, **kwargs)
    
    # Replace the classes globally
    msgpack.Packer = PatchedPacker
    msgpack.Unpacker = PatchedUnpacker
    msgpack._encoding_patch_applied = True
