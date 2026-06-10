import sys
import asyncio

def patch_all_readlines():
    patched_count = 0
    # Search through all loaded modules
    for module_name, module in list(sys.modules.items()):
        if not module: continue
        for attr_name in dir(module):
            try:
                obj = getattr(module, attr_name)
                if isinstance(obj, type) and hasattr(obj, 'readline') and callable(getattr(obj, 'readline')):
                    # Check if it's an async method (usually the case for StreamReader)
                    original_readline = obj.readline
                    if hasattr(original_readline, "__is_patched__"):
                        continue
                        
                    async def make_patch(orig):
                        async def patched_readline(self, *args, **kwargs):
                            kwargs.pop('max_line_length', None)
                            return await orig(self, *args, **kwargs)
                        return patched_readline

                    # We apply the patch to the class
                    new_readline = asyncio.run(make_patch(original_readline)) if not asyncio.iscoroutinefunction(original_readline) else None
                    # Wait, we need to be careful with asyncio.run here. 
                    # Let's just define the async function directly.
                    
                    async def patched_readline(self, *args, **kwargs):
                        kwargs.pop('max_line_length', None)
                        # We need to handle both sync and async original_readline
                        import inspect
                        if inspect.iscoroutinefunction(original_readline):
                            return await original_readline(self, *args, **kwargs)
                        else:
                            return original_readline(self, *args, **kwargs)

                    patched_readline.__is_patched__ = True
                    obj.readline = patched_readline
                    patched_count += 1
            except:
                continue
    print(f"Patched {patched_count} 'readline' methods across loaded modules.")

if __name__ == "__main__":
    # Import some common libraries first to ensure they are in sys.modules
    import asyncio.streams
    try: import anyio._backends._asyncio
    except: pass
    try: import httpcore._async.http11
    except: pass
    
    patch_all_readlines()
