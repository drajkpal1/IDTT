# server.py
from asyncua import ua, Server
import asyncio

async def main():
    # Setup server
    server = Server()
    await server.init()
    # Server Endpoints. Replace with your desired URL
    server.set_endpoint("opc.tcp://localhost:4840/")
    
    # Set up own namespace
    uri = "http://example.uri.github.io"
    idx = await server.register_namespace(uri)
    
    # Get Objects node for populating custom stuff
    object_node = server.get_objects_node()
  
    # Populating address space with a folder and variables
    workstation_details = await object_node.add_folder(idx, "workstation_details")
    
    total_blocks_var = await workstation_details.add_variable(ua.NodeId("TB", idx), "Total_blocks", 0)
    await total_blocks_var.set_writable()
    
    drilled_blocks_var = await workstation_details.add_variable(ua.NodeId("DIB", idx), "Drilled_blocks", 0)    
    await drilled_blocks_var.set_writable()
    
    damaged_blocks_var = await workstation_details.add_variable(ua.NodeId("DMB", idx), "Damaged_blocks", 0)
    await damaged_blocks_var.set_writable()

    drilling_time_var = await workstation_details.add_variable(ua.NodeId("DRILL", idx), "MotorOn_time", 0.0)
    await drilling_time_var.set_writable()
    @uamethod
    async def show_values(parent):
        tb_val = await total_blocks_var.read_value()
        dib_val = await drilled_blocks_var.read_value()
        dmb_val = await damaged_blocks_var.read_value()
        run_val = await workstation_running_status_var.read_value()
        return f"Ejected_blocks: {tb_val}, Drilled_blocks: {dib_val}, Damaged_blocks: {dmb_val}, Workstation_running: {run_val}"
    
    # Add the method to the custom object
    await myobject.add_method(idx, 'show_values', show_values, [], [ua.VariantType.String])

    # Start server
    await server.start()
    
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(lambda x, y: None)  # Silently consume exceptions
    loop.run_until_complete(main())
    loop.run_forever()