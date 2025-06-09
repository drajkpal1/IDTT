from pyModbusTCP.client import ModbusClient
from pyModbusTCP.utils import set_bit, reset_bit, test_bit
from time import sleep
import multiprocessing
import paho.mqtt.publish as publish
from coapthon.server.coap import CoAP
from coapthon.resources.resource import Resource
import logging

# Configure logging for CoAP server
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WorkstationModule:
    # Constants
    DIGITAL_INPUT_STARTING_ADDRESS = 8001
    DIGITAL_OUTPUT_STARTING_ADDRESS = 8003

    def __init__(self, ip_addr, sem_output=None, sem_self_turning=None, sem_opposite_turning=None, read_write_sem=None):
        """
        Constructor of the WorkstationModules.

        :param ip_addr: IP address of the Modbus node used for the workstation (String)
        :param sem_output: Semaphore for checking if the exit is currently free (optional)
        :param sem_self_turning: Semaphore to indicate if the station's table is turning (optional)
        :param sem_opposite_turning: Semaphore to indicate if the opposite station's table is turning (optional)
        :param read_write_sem: Semaphore to ensure mutual exclusion for read/write operations (optional)
        """

        try:
            # Establish connection to Modbus with the provided IP address
            self.client = ModbusClient(host=ip_addr, auto_open=True, auto_close=True)
        except ValueError:
            print("Error with host param")

        # Identifier based on the IP address
        self.identifier = 'B' + ip_addr.split('.')[-1]

        self.sem_output = sem_output
        self.sem_self_turning = sem_self_turning
        self.sem_opposite_turning = sem_opposite_turning

        # Semaphore for internal synchronization
        self.sem = multiprocessing.BoundedSemaphore(value=1)
        self.read_write_sem = read_write_sem

    # Methods to interact with Modbus registers

    def get_output_register(self, offset=0, amount=1):
        """
        Returns the output registers of the Modbus.

        :param offset: Offset to DIGITAL_OUTPUT_STARTING_ADDRESS
        :param amount: Amount of registers to read
        :return: List of read registers (or None if it fails)
        """
        with self.read_write_sem:
            result = None
            while result is None:
                result = self.client.read_holding_registers(reg_addr=self.DIGITAL_OUTPUT_STARTING_ADDRESS + offset,
                                                            reg_nb=amount)
            return result

    def set_output_register(self, register, offset=0):
        """
        Overwrites the output register of the Modbus.

        :param register: List of integers to write to the registers
        :param offset: Offset to DIGITAL_OUTPUT_STARTING_ADDRESS
        """
        with self.read_write_sem:
            result = None
            while result is None:
                result = self.client.write_multiple_registers(self.DIGITAL_OUTPUT_STARTING_ADDRESS + offset, register)
            return result

    def checker_down(self):
        """
        Drives the checker down.
        """
        with self.sem:
            reg = self.get_output_register()
            reg[0] = set_bit(reg[0], 5)
            self.set_output_register(reg)

    def checker_up(self):
        """
        Drives the checker up.
        """
        with self.sem:
            reg = self.get_output_register()
            reg[0] = reset_bit(reg[0], 5)
            self.set_output_register(reg)

    def publish_mqtt_data(self, total_blocks, drilled_blocks, damaged_blocks):
        """
        Publishes data to MQTT broker.

        :param total_blocks: Total number of blocks
        :param drilled_blocks: Number of drilled blocks
        :param damaged_blocks: Number of damaged blocks
        """
        hostname = "localhost"
        publish.single("Total block", total_blocks, hostname=hostname)
        publish.single("Drilled block", drilled_blocks, hostname=hostname)
        publish.single("Damaged block", damaged_blocks, hostname=hostname)

# CoAP resource for controlling checker station
class CheckerResource(Resource):
    def __init__(self, name="CheckerResource", coap_server=None):
        super(CheckerResource, self).__init__(name, coap_server, visible=True, observable=True, allow_children=False)

    def render_POST(self, request):
        """
        Handles POST requests to control the checker station.

        :param request: CoAP request
        :return: CoAP response
        """
        payload = request.payload.decode('utf-8')
        if payload == "up":
            workstation.checker_up()
            logger.info("Checker moved up")
            return self
        elif payload == "down":
            workstation.checker_down()
            logger.info("Checker moved down")
            return self
        else:
            logger.warning("Invalid payload received")
            return None

# Instantiate CoAP server
coap_server = CoAP(("0.0.0.0", 5683))
workstation = WorkstationModule("192.168.200.234")

# Register CoAP resources
coap_server.add_resource("checker/", CheckerResource())

# Start CoAP server in a separate thread
coap_server.listen()

# Example usage: continuously work and publish data
def work_and_publish():
    drilled = 0
    damaged = 0
    while True:
        # Simulate working process
        sleep(2)  # Simulate processing time

        # Example logic to determine number of blocks
        drilled += 1
        damaged += 0  # Simulate no damaged blocks for simplicity

        # Publish MQTT data
        workstation.publish_mqtt_data(drilled + damaged, drilled, damaged)

# Run the work and publish loop in a separate process
if __name__ == "__main__":
    multiprocessing.Process(target=work_and_publish).start()
