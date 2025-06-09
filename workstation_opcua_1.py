from pyModbusTCP.client import ModbusClient
from pyModbusTCP.utils import get_bits_from_int
from pyModbusTCP.utils import set_bit
from pyModbusTCP.utils import reset_bit
from pyModbusTCP.utils import test_bit
from time import sleep
import datetime
import multiprocessing
from asyncua import Client
import asyncio
import time

async def main(total_blocks, drilled_blocks, damaged_blocks, drilling_time):
    # URL setup. Replace with your server's endpoint:
    url = "opc.tcp://localhost:4840/"

    # Setup client
    client = Client(url=url)
    await client.connect()

    # Get namespace index
    uri = "http://example.uri.github.io"
    idx = await client.get_namespace_index(uri)
    
 # Get reference to our variables using their node ids:
    total_blocks_var = client.get_node(f"ns={idx};s=TB")
    drilled_blocks_var = client.get_node(f"ns={idx};s=DIB")
    damaged_blocks_var = client.get_node(f"ns={idx};s=DMB")
    drilling_time_var = client.get_node(f"ns={idx};s=DRILL")
    
    # Set new values for variables
    await total_blocks_var.set_value(total_blocks)
    await drilled_blocks_var.set_value(drilled_blocks)
    await damaged_blocks_var.set_value(damaged_blocks)
    await drilling_time_var.set_value(drilling_time)

    # Disconnect the client
    await client.disconnect()

class WorkstationModule:
    #Konstanten
    DIGITAL_INPUT_STARTING_ADDRESS = 8001
    DIGITAL_OUTPUT_STARTING_ADDRESS = 8003

    def __init__(self, ip_addr, sem_output : multiprocessing.BoundedSemaphore = None, sem_self_turning : multiprocessing.BoundedSemaphore = None, sem_opposite_turning : multiprocessing.BoundedSemaphore = None, read_write_sem = multiprocessing.BoundedSemaphore(value=1)):
        """
        Konstruktor of the WorkstationModules.

        :param ip_addr Ip-adress of the modbus node, which is used for the workstation (String)
        :param sem_output Semaphore for checking if the exit is currently free (doesnt have to be used)
        :param sem_selbst_drehen Semaphore to show if the stations table is currently turning (the opposite station cant use the exit while the table is turning)
        :param sem_opposite_turning  Semaphore to see if the oposite stations table is currently turning (this station cant use the exit while the table of the other station is turning)
        :param read_write_sem Semaphore that can be used to make sure that 2 modules cant read/write at the same time.
        """

        try:
            #Erzeugt eine Verbindung zum Modbus mit der ip_addr
            self.client = ModbusClient(host=ip_addr, auto_open=True, auto_close=True)
        except ValueError:
            print("Error with host param")

        #Setzt alle Output Bits auf 0
        #self.client.write_multiple_registers(self.DIGITAL_OUTPUT_STARTING_ADDRESS, [0])

        self.identifier = 'B' + ip_addr[len(ip_addr)-1]
        
        self.sem_output = sem_output
        self.sem_self_turning = sem_self_turning
        self.sem_opposite_turning = sem_opposite_turning

        self.sem = multiprocessing.BoundedSemaphore(value=1)
        self.read_write_sem = read_write_sem

    def get_output_register(self, offset = 0, amount = 1):
        """
        Returns the output registers of the modbus.

        :param offset Offset to DIGITAL_OUTPUT_STARTING_ADDRESS
        :param amount Amount of registers that can be read
        :returns list of read registers (or nothing if it fails)
        :rtype list of int or none
        """
        with self.read_write_sem:
            result = None
            while result == None:
                result = self.client.read_holding_registers(reg_addr=self.DIGITAL_OUTPUT_STARTING_ADDRESS + offset,reg_nb = amount)
            return result

    def get_input_register(self, offset = 0, amount = 1):
        """
        Returns the input registers of the modbus.

        :param offset Offset to DIGITAL_INPUT_STARTING_ADDRESS
        :param amount Amount of registers that can be read
        :returns list of read registers (or nothing if it fails)
        :rtype list of int or none
        """
        with self.read_write_sem:
            result = None
            while result == None:
                result = self.client.read_holding_registers(reg_addr=self.DIGITAL_INPUT_STARTING_ADDRESS + offset,reg_nb = amount)
            return result

    def set_output_register(self, register, offset = 0):
        """
        Overwrites the output register of the modbus.

        :param register list of int that should be written to the registers
        :param offset Offset to DIGITAL_OUTPUT_STARTING_ADDRESS
        """
        with self.read_write_sem:
            result = None
            while result == None:
                result = self.client.write_multiple_registers(self.DIGITAL_OUTPUT_STARTING_ADDRESS + offset, register)
            return result

    def drill_on(self):
        """
        Turns on the drill
        """
        with self.sem:
            reg = self.get_output_register()
            reg[0] = set_bit(reg[0], 0)
            self.set_output_register(reg)
        

    def drill_off(self):
        """
        Turns of the drill
        """
        with self.sem:
            reg = self.get_output_register()
            reg[0] = reset_bit(reg[0],0)
            self.set_output_register(reg)

    def drill_up(self):
        """
        Drives the drill up
        """
        with self.sem:
            reg = self.get_output_register()
            reg[0] = reset_bit(reg[0], 2)
            reg[0] = set_bit(reg[0], 3)
            self.set_output_register(reg)
    
    def drill_down(self):
        """
        Drives the drill down
        """
        with self.sem:
            reg = self.get_output_register()
            reg[0] = reset_bit(reg[0], 3)
            reg[0] = set_bit(reg[0], 2)
            self.set_output_register(reg)

    def drill_stop(self):
        """
        Stops the vertical movement of the drill.
        """
        with self.sem:
            reg = self.get_output_register()
            reg[0] = reset_bit(reg[0], 2)
            reg[0] = reset_bit(reg[0], 3)
            self.set_output_register(reg)

    def lock_piece(self):
        """
        Activates the lock for the pieces under the drill.
        """
        with self.sem:
            reg = self.get_output_register()
            reg[0] = set_bit(reg[0], 4)
            self.set_output_register(reg)

    def unlock_piece(self):
        """
        Deactivates the lock for the pieces under the drill.
        """
        with self.sem:
            reg = self.get_output_register()
            reg[0] = reset_bit(reg[0], 4)
            self.set_output_register(reg)

    def turntable_on(self):
        """
        Starts the turntable.
        """
        with self.sem:
            reg = self.get_output_register()
            reg[0] = set_bit(reg[0], 1)
            self.set_output_register(reg)

    def turntable_off(self):
        """
        Stops the turntable.
        """
        with self.sem:
            reg = self.get_output_register()
            reg[0] = reset_bit(reg[0], 1)
            self.set_output_register(reg)

    def turntable_turn_single(self):
        """
        Turns the turn table exactly for one position
        """
        with self.sem:
            reg = self.get_output_register()
            reg[0] = set_bit(reg[0], 1)
            self.set_output_register(reg)
            sleep(0.1)
            reg[0] = reset_bit(reg[0], 1)
            self.set_output_register(reg)

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

    def ejector_output_extend(self):
        """
        Activates the ejactor at the exit.
        """
        with self.sem:
            reg = self.get_output_register()
            reg[0] = set_bit(reg[0], 6)
            self.set_output_register(reg)

    def ejector_input_extend(self):
        """
         Activates the ejactor at the input.
        """
        with self.sem:
            reg = self.get_output_register()
            reg[0] = set_bit(reg[0], 7)
            self.set_output_register(reg)

    def ejector_output_retract(self):
        """
        Deactivates the ejactor at the exit.
        """
        with self.sem:
            reg = self.get_output_register()
            reg[0] = reset_bit(reg[0], 6)
            self.set_output_register(reg)

    def ejector_input_retract(self):
        """
        Deactivates the ejactor at the exit.
        """
        with self.sem:
            reg = self.get_output_register()
            reg[0] = reset_bit(reg[0], 6)
            self.set_output_register(reg)

    def check_workpiece_sensor(self, sensor_id):
        """
        checks the workpiece sensor specified in the parameter. If the sensor is activated this function returns true,
        otherwise it returns false. If a unspecified sensor number is used, it will always return false.
        1-Turntable entrance
        2-Checker station
        3-Drill

        :param sensor_id Number of sensor to be checked (1-3)
        :returns boolean to see if the sensor was activated
        :rtype bool
        """

        #Nummer 1 und 2 werden getauscht damit die Nummerrierung zur Annordnung der Anlage passt 
        if sensor_id == 2:
            sensor_id = 3
        elif sensor_id == 3:
            sensor_id = 2
        elif sensor_id != 1:
            return False

        return test_bit(self.get_input_register()[0], sensor_id-1)

    def check_drill_up(self):
        """
        Checks if the drill is up, if yes, this function returns true.
        Returns false, if the drill is not up OR the flag to set the drill up is not set. 
        (as an example if the drill is stopped with drill_stop())
        :returns boolean if the drill is up
        :rtype bool
        """
        return test_bit(self.get_input_register()[0], 3)

    def check_drill_down(self):
        """
        Checks if the drill is up, if yes, this function returns true.
        Returns false, if the drill is not up OR the flag to set the drill up is not set. 
        (as an example if the drill is stopped with drill_stop())
        :returns boolean if the drill is up
        :rtype bool
        """
        return test_bit(self.get_input_register()[0], 4)

    def check_turntable_position(self):
        """
        Überprüft, ob der Drehteller in Position ist, wenn ja wird True zurückgegeben.
        :returns boolean ob Drehteller in Position ist
        :rtype bool
        """
        return test_bit(self.get_input_register()[0], 5)

    def check_workpiece(self):
        """
        Überprüft, ob der der Prüfer ein Werkstück in Normallage erkennt, wenn ja wird True zurückgegeben.
        :returns boolean ob Prüfer ein Werkstück in Normallage erkennt
        :rtype bool
        """
        return test_bit(self.get_input_register()[0], 6)

    def work(self, queue_to_TS = None):
        drilled=0
        damaged=0
        drilling_time=0.0

        workpiece_ok = False           #Zeigt dass ein Werkstück in Normalposition geprüft wurde -> bohren
        workpiece_nok = False         #Stellt dar dass sich ein umgedrehtes Werkstück im Prüfer befindet -> Extra Drehung
        workpiece_nok_drill = False  #Stellt dar dass sich ein umgedrehtes Werkstück im Bohrer befindet -> Extra drehung und auswerfen
        workpiece_eject = False        #Zeigt dass sich ein Werkstück im Ausgang befindet -> auswerfern
        workpiece_nok_output = False #Zeigt dass sich ein umgedrehtes Werkstück im Ausgang befindet -> wird nach DZA und nicht nach WA transportiert

        while True:
            
            #Wartet bis ein Werkstück durch einen Sensor erkannt wird. (Oder sich noch ein Werkstück in abnormaler Position in der Station befindet)
            
            while not self.check_turntable_position or (not self.check_workpiece_sensor(1) and not self.check_workpiece_sensor(2) and not self.check_workpiece_sensor(3) and not workpiece_nok and not workpiece_nok_drill):
                sleep(0.5) 

            sum = drilled + damaged

            if __name__ == "__main__":
                loop = asyncio.get_event_loop()
                loop.set_exception_handler(lambda x, y: None)  # Silently consume exceptions
                loop.run_until_complete(main(sum, drilled, damaged, drilling_time))

            #Dient dazu der gegenüberliegenden Bearbeitenstation zu signalisieren dass diese Bearbeitenstation sich dreht und die
            #gegenüberliegende gerade nicht auswerfen sollte (eventuell überarbeiten um weniger Semaphoren zu benutzen)
            if self.sem_self_turning != None:
                self.sem_self_turning.acquire()

            if self.check_workpiece_sensor(3) or workpiece_nok_drill:
                if workpiece_nok_drill:
                    workpiece_nok_output = True
                workpiece_eject = True
                workpiece_nok_drill = False
            if workpiece_nok:
                workpiece_nok = False
                workpiece_nok_drill= True
            
            #Drehteller dreht um eine Position, und es wird gewartet bis der Drehteller wieder in Position ist
            self.turntable_turn_single()
            while not self.check_turntable_position():
                sleep(0.1)

            #Signalisiert der gegenüberliegenden Bearbeitenstation dass die Drehung zuende ist
            if self.sem_self_turning != None:
                self.sem_self_turning.release()
            
            #Es wird unabhängig davon geprüft ob ein Werkstück im Prüfer erkannt wird,
            #da Werkstücke in abnormaler Position von den Sensoren nicht erkannt werden,
            # aber vom prüfer als nicht normal erkannt werden können.   
            self.checker_down()
        
            if workpiece_eject:
                self.ejector_output_extend()  # Activate the output ejector
                
            #Befindet sich ein Werkstück am Ausgang wird dieses ausgeworfen.
            if workpiece_eject == True:
                if self.sem_output != None:
                    self.sem_output.acquire()

                if self.sem_opposite_turning != None:
                    self.sem_opposite_turning.acquire()

                if queue_to_TS != None:
                    if workpiece_nok_output:
                        workpiece_nok_output = False
                        queue_to_TS.put([self.identifier, 'DZA']) #falsch gedrehte Werkstücke nach DZA
                    else:
                        queue_to_TS.put([self.identifier, 'WA']) #richtig gedrehte Werkstücke nach WA

                self.ejector_output_retract()     

            #Befindet sich in der Bohrstation ein Werkstück in Normalposition wird dieses gebohrt.
            #Dabei wird gewartet bis der Bohrer unten ist. Wird nicht gebohrt, dann wird 0.35 Sekunden gewartet,
            #damit Prüfer und Auswerfer ihre Bewegung durchführen können bevor dies abgebrochen wird.
            if self.check_workpiece_sensor(3) and workpiece_ok:
                self.lock_piece()
                self.drill_on()
                measure = 1.405
                drilling_time = drilling_time + measure
                if __name__ == "__main__":
                    loop = asyncio.get_event_loop()
                    loop.set_exception_handler(lambda x, y: None)  # Silently consume exceptions
                    loop.run_until_complete(main(sum, drilled, damaged, drilling_time))
                self.drill_down()
                while not self.check_drill_down():
                    sleep(0.1)
            else:
                sleep(0.35)
            #Bohrvorgang wird beendet
            if self.check_workpiece_sensor(3) and workpiece_ok:
                self.unlock_piece()
                self.drill_up()
                drilled+=1
                self.drill_off()
                sleep(0.1)
            
            workpiece_ok = False

            #Überprüfung findet statt, ob sich ein abnormales Werkstück im Prüfer befindet   
            if self.check_workpiece():
                workpiece_ok = True
            else:
                workpiece_nok = True
                damaged+=1
            self.checker_up()

            if workpiece_eject:
                if self.sem_opposite_turning != None:
                    self.sem_opposite_turning.release()

                self.ejector_input_retract()
                workpiece_eject = False


workstation = WorkstationModule("192.168.200.234")

workstation.work()




