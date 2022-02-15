from requests.auth import HTTPBasicAuth
from requests import Session
from ast import literal_eval
import json, time, pathlib

class RWS:
    """Class for communicating with RobotWare through Robot Web Services (ABB's Rest API).
    This class was built on the foundation of the work done in https://github.com/prinsWindy/ABB-Robot-Machine-Vision, and have been modified and expanded on as a tool in my master's thesis work.
    "For the RW 7.0 release, RWS has introduced several breaking changes to include the following requirements" -> Updates
    """

    def __init__(self, base_url, username='admin', password='robotics', headers = {'Content-Type':'application/x-www-form-urlencoded;v=2.0'}, headers2 = {'accept': 'application/hal+json;v=2.0'}, verify = False, task = 'T_ROB1', module = 'mainModule'):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.session = Session() # create persistent HTTP communication
        self.session.auth = HTTPBasicAuth(self.username, self.password)
        self.headers = headers
        self.headers_json = headers2
        self.verify = verify
        self.task = task
        self.module = module

    def get_modules(self, ignore=True, api=False):
        """"
        Get name of non-SysMod loaded modules
        """
        resp = self.session.get(f'{self.base_url}/rw/rapid/tasks/{self.task}/modules', headers=self.headers_json, auth=self.session.auth, verify=self.verify)
        if resp.status_code == 200:
            v = [mod["name"] for mod in json.loads(resp.text)["state"] if ignore and mod["type"] != "SysMod"]
            return (v, resp) if api else v
        else:
            print(f"Call might have failed\nstatus: {resp.status_code}\nbody: {resp.text}")
            return resp

    def load_RAPID(self, path='$HOME/'):
        """
        loads RAPID _program_ from path
        """
        resp = self.session.post(f'{self.base_url}/rw/rapid/tasks/{self.task}/program/load', headers=self.headers, data={'progpath': path}, auth=self.session.auth, verify=self.verify)
        return resp

    def write_array(self, name, li, type='VAR', subtype='jointtarget', mod='arrs_mod', path=''):
        """
        Method for adding array into module of saved arrays
        NB! li (the values) must be formatted correctly (according to RAPID)
        NB! will overwrite variables
        NB! no variable name can be the postscript of an earlier variable, such a variable will be overwritten
        NB! SLOW code
        """
        p=pathlib.Path(path,f"{mod}.modx")
        try: 
            with open(p, 'r+') as f:
                lines = f.readlines()
                f.seek(0)
                for line in lines: #did not manage to do this in the while below
                    if f"{name}{{" not in line:
                        f.write(line)
                f.truncate()
                f.seek(0)
                pos, text = 0, ''
                while True: #SO magic
                    # save last line value and cursor position
                    prev_pos, pos = pos, f.tell()
                    prev_text, text = text, f.readline()
                    if text == '':
                        break
                f.seek(prev_pos, 0) # replace cursor to the last line
                if subtype in ['speeddata', 'zonedata']:
                    f.write(f"\t{type} {subtype} {name}{{{len(li)}}} := {str(li)};\n".replace("'",""))
                else:
                    f.write(f"\t{type} {subtype} {name}{{{len(li)}}} := {str(li)};\n")
                f.write(prev_text) # write old last line
        except OSError:
            with open(p, 'w+') as f:
                f.write(f"MODULE {mod}\nENDMODULE")
            self.write_array(name, li, path, type, subtype, mod)
        
            

    def load_module(self, name='arrs_mod', overwrite=True, path='$HOME/'):
        """"
        loads module from (RWS?) relative path
        NB! overwrites by default
        """
        if overwrite is True:
            resp = self.session.post(f'{self.base_url}/rw/rapid/tasks/{self.task}/unloadmod', headers=self.headers, data={'module': name}, auth=self.session.auth, verify=self.verify)
            if resp.status_code != 204:
                print('Unload module might have failed')
        resp = self.session.post(f'{self.base_url}/rw/rapid/tasks/{self.task}/loadmod', headers=dict(self.headers, **self.headers_json), data={'modulepath': f"{path}{name}.modx"}, auth=self.session.auth, verify=self.verify)
        return resp

    def set_rapid_variable(self, var, value, initval='false'):
        """
        Sets the value of any RAPID variable.
        Unless the variable is of type 'num', 'value' has to be a string.
        Actually works somehow
        """
        params = (
            ('initval', initval),
        )
        payload = {'value': value}
        resp = self.session.post(f"{self.base_url}/rw/rapid/symbol/RAPID/{self.task}/{self.module}/{var}/data", verify=self.verify, data=payload, headers=self.headers, auth=self.session.auth, params=params)
        return resp

    def get_rapid_variable_properties(self, var):
        """
        Not useful atm
        Gets the properties of any RAPID variable.
        TODO: json parsing
        """
        resp = self.session.get(f"{self.base_url}/rw/rapid/symbol/RAPID/{self.task}/{self.module}/{var}/properties", verify=self.verify, headers=self.headers_json, auth=self.session.auth)
        return resp

    def get_rapid_variable(self, var, api=False):
        """
        Gets the value of any RAPID variable.
        """
        resp = self.session.get(f"{self.base_url}/rw/rapid/symbol/RAPID/{self.task}/{self.module}/{var}/data", verify=self.verify, headers=self.headers_json, auth=self.session.auth)
        if resp.status_code == 200:
            v = json.loads(resp.text)["state"][0]["value"]
            return (v, resp) if api else v
        else:
            print(f"Call for variable {var} might have failed\nstatus: {resp.status_code}\nbody: {resp.text}")
            return resp

    def get_robtarget_variables(self, var):
        """
        NOT UPDATED, doesn't work
        Gets both translational and rotational data from robtarget.
        TODO: update or remove
        """

        resp = self.session.get(self.base_url + '/rw/rapid/symbol/data/RAPID/T_ROB1/' + var + ';value?json=1')
        json_string = resp.text
        _dict = json.loads(json_string)
        data = _dict["_embedded"]["_state"][0]["value"]
        data_list = literal_eval(data)  # Convert the pure string from data to list
        trans = data_list[0]  # Get x,y,z from robtarget relative to work object (table)
        rot = data_list[1]  # Get orientation of robtarget
        return trans, rot

    def get_gripper_position(self):
        """
        NOT UPDATED, doesn't work
        Gets translational and rotational of the UiS tool 'tGripper'
        with respect to the work object 'wobjTableN'.
        """

        resp = self.session.get(self.base_url +
                                '/rw/motionsystem/mechunits/ROB_1/robtarget/'
                                '?tool=tGripper&wobj=wobjTableN&coordinate=Wobj&json=1')
        json_string = resp.text
        _dict = json.loads(json_string)
        data = _dict["_embedded"]["_state"][0]
        trans = [data["x"], data["y"], data["z"]]
        trans = [float(i) for i in trans]
        rot = [data["q1"], data["q2"], data["q3"], data["q4"]]
        rot = [float(i) for i in rot]

        return trans, rot

    def get_gripper_height(self):
        """
        NOT UPDATED, doesn't work
        Extracts only the height from gripper position.
        (See get_gripper_position)
        """

        trans, rot = self.get_gripper_position()
        height = trans[2]

        return height

    def set_robtarget_translation(self, var, trans):
        """
        NOT UPDATED, doesn't work
        Sets the translational data of a robtarget variable in RAPID.
        """

        _trans, rot = self.get_robtarget_variables(var)
        if rot == [0, 0, 0, 0]:  # If the target has no previously defined orientation
            self.set_rapid_variable(var, "[[" + ','.join(
                [str(s) for s in trans]) + "],[0,1,0,0],[-1,0,0,0],[9E+9,9E+9,9E+9,9E+9,9E+9,9E+9]]")
        else:
            self.set_rapid_variable(var, "[[" + ','.join(
                [str(s) for s in trans]) + "],[" + ','.join(str(s) for s in rot) + "],[-1,0,0,0],[9E+9,9E+9,9E+9,9E+9,"
                                                                                   "9E+9,9E+9]]")

    def set_robtarget_rotation_z_degrees(self, var, rotation_z_degrees):
        """
        NOT UPDATED, doesn't work
        Updates the orientation of a robtarget variable
        in RAPID by rotation about the z-axis in degrees.
        """

        rot = z_degrees_to_quaternion(rotation_z_degrees)

        trans, _rot = self.get_robtarget_variables(var)

        self.set_rapid_variable(var, "[[" + ','.join(
            [str(s) for s in trans]) + "],[" + ','.join(str(s) for s in rot) + "],[-1,0,0,0],[9E+9,9E+9,9E+9,9E+9,"
                                                                               "9E+9,9E+9]]")

    def set_robtarget_rotation_quaternion(self, var, rotation_quaternion):
        """
        NOT UPDATED, doesn't work
        Updates the orientation of a robtarget variable in RAPID by a Quaternion.
        """

        trans, _rot = self.get_robtarget_variables(var)

        self.set_rapid_variable(var, "[[" + ','.join(
            [str(s) for s in trans]) + "],[" + ','.join(str(s) for s in rotation_quaternion) + "],[-1,0,0,0],[9E+9,"
                                                                                               "9E+9,9E+9,9E+9,9E+9,"
                                                                                               "9E+9]]")

    def wait_for_rapid(self, var='ready_flag'):
        """
        Waits for robot to complete RAPID instructions
        until boolean variable in RAPID is set to 'TRUE'.
        Default variable name is 'ready_flag', but others may be used.
        TODO:  matter?
        """
        while self.get_rapid_variable(var) == "FALSE" or self.is_running():
            time.sleep(0.1)
        self.set_rapid_variable('ready_flag', 'FALSE')

    def set_rapid_array(self, var, value):
        """
        NOT UPDATED, doesn't work
        Sets the values of a RAPID array by sending a list from Python.
        TODO: update to new RWS
        """

        # TODO: Check if array must be same size in RAPID and Python
        self.set_rapid_variable(var, "[" + ','.join([str(s) for s in value]) + "]")

    def reset_pp(self):
        """
        Resets the program pointer to main procedure in RAPID.
        """
        resp = self.session.post(self.base_url + '/rw/rapid/execution/resetpp', auth=self.session.auth, verify=self.verify, headers=self.headers)
        return resp

    def toggle_mastership(self, tog = 0):
        """
        toggles write-permission (if allowed)
        Accepts 0 or 1 as input.
        """
        resp = self.session.post(self.base_url + '/rw/mastership/' + ['release', 'request'][tog], verify=self.verify, auth=self.session.auth, headers=self.headers)
        return resp
    
    def request_rmmp(self):
        """NOT UPDATED, doesn't work"""
        resp = self.session.post(self.base_url + '/users/rmmp', data={'privilege': 'modify'})

    def cancel_rmmp(self):
        """NOT UPDATED, doesn't work"""
        resp = self.session.post(self.base_url + '/users/rmmp?action=cancel')

    def toggle_motors(self, tog=0):
        """
        Toggles the robot's motors.
        Accepts 0 or 1 as input.
        Operation mode has to be AUTO.
        """
        payload = {'ctrl-state': ['motoroff', 'motoron'][tog]}
        resp = self.session.post(self.base_url + "/rw/panel/ctrl-state", data=payload, headers=self.headers, auth=self.session.auth, verify=self.verify)
        return resp
    def start_RAPID_prod(self):
        """
        Semi-broken & Unnecessary
        TODO: remove?
        """
        self.reset_pp()
        resp = self.session.post(self.base_url + "/rw/rapid/execution/startprodentry",  headers=self.headers, auth=self.session.auth, verify=self.verify)
        return resp

    def start_RAPID(self):
        """
        Resets program pointer to main procedure in RAPID and starts RAPID execution.
        mastership:implicit very important
        Cannot run execution/start with mastership, but mastership is requred for /resetpp. weird.
        """
        self.toggle_mastership(1)
        self.reset_pp()
        self.toggle_mastership(0)
        params = (
            ('mastership', 'implicit'),
        )
        payload = {
            'regain': 'continue',
            'execmode': 'continue',
            'cycle': 'once',
            'condition': 'none',
            'stopatbp': 'disabled',
            'alltaskbytsp': 'false'
        }
        resp = self.session.post(self.base_url + "/rw/rapid/execution/start", data=payload, headers=self.headers, auth=self.session.auth, verify=self.verify, params=params)
        return resp

    def stop_RAPID(self):
        """
        NOT UPDATED, doesn't work
        Stops RAPID execution.
        TODO: update to new RWS
        """

        payload = {'stopmode': 'stop', 'usetsp': 'normal'}
        resp = self.session.post(self.base_url + "/rw/rapid/execution?action=stop", data=payload)
        if resp.status_code == 204:
            print('RAPID execution stopped')
        else:
            print('Could not stop RAPID execution')

    def get_exec_state(self, api=False):
        """Gets the execution state of the controller.
        """

        resp = self.session.get(f"{self.base_url}/rw/rapid/execution", headers=self.headers_json, auth=self.session.auth, verify=self.verify)
        if resp.status_code == 200:
            v = json.loads(resp.text)["state"][0]["ctrlexecstate"]
            return (v, resp) if api else v
        else:
            print(f"Call might have failed\nstatus: {resp.status_code}\nbody: {resp.text}")
            return resp

    def is_running(self):
        """Checks the execution state of the controller and
        """
        return True if self.get_exec_state() == "running" else False

    def get_operation_mode(self):
        """
        NOT UPDATED, doesn't work
        Gets the operation mode of the controller.
        TODO: update or remove
        """

        resp = self.session.get(self.base_url + "/rw/panel/opmode?json=1")
        json_string = resp.text
        _dict = json.loads(json_string)
        data = _dict["_embedded"]["_state"][0]["opmode"]
        return data

    def get_controller_state(self):
        """
        NOT UPDATED, doesn't work
        Gets the controller state.
        TODO: update or remove
        """

        resp = self.session.get(self.base_url + "/rw/panel/ctrlstate?json=1")
        json_string = resp.text
        _dict = json.loads(json_string)
        data = _dict["_embedded"]["_state"][0]["ctrlstate"]
        return data

    def set_speed_ratio(self, speed_ratio):
        """
        NOT UPDATED, might work
        Sets the speed ratio of the controller.
        TODO: update or remove
        """

        if not 0 < speed_ratio <= 100:
            print("You have entered a false speed ratio value! Try again.")
            return

        payload = {'speed-ratio': speed_ratio}
        resp = self.session.post(self.base_url + "/rw/panel/speedratio?action=setspeedratio", data=payload)
        if resp.status_code == 204:
            print(f'Set speed ratio to {speed_ratio}%')
        else:
            print('Could not set speed ratio!')

    def set_zonedata(self, var, zonedata):
        """
        NOT UPDATED, might work
        Sets the zonedata of a zonedata variable in RAPID.
        TODO: update or remove
        """

        if zonedata not in ['fine', 0, 1, 5, 10, 20, 30, 40, 50, 60, 80, 100, 150, 200]:
            print("You have entered false zonedata! Please try again")
            return
        else:
            if zonedata in [10, 20, 30, 40, 50, 60, 80, 100, 150, 200]:
                value = f'[FALSE, {zonedata}, {zonedata * 1.5}, {zonedata * 1.5}, {zonedata * 0.15}, ' \
                        f'{zonedata * 1.5}, {zonedata * 0.15}]'
            elif zonedata == 0:
                value = f'[FALSE, {zonedata + 0.3}, {zonedata + 0.3}, {zonedata + 0.3}, {zonedata + 0.03}, ' \
                        f'{zonedata + 0.3}, {zonedata + 0.03}]'
            elif zonedata == 1:
                value = f'[FALSE, {zonedata}, {zonedata}, {zonedata}, {zonedata * 0.1}, {zonedata}, {zonedata * 0.1}]'
            elif zonedata == 5:
                value = f'[FALSE, {zonedata}, {zonedata * 1.6}, {zonedata * 1.6}, {zonedata * 0.16}, ' \
                        f'{zonedata * 1.6}, {zonedata * 0.16}]'
            else:  # zonedata == 'fine':
                value = f'[TRUE, {0}, {0}, {0}, {0}, {0}, {0}]'

        resp = self.set_rapid_variable(var, value)
        if resp.status_code == 204:
            print(f'Set \"{var}\" zonedata to z{zonedata}')
        else:
            print('Could not set zonedata! Check that the variable name is correct')

    def set_speeddata(self, var, speeddata):
        """
        NOT UPDATED, might work
        Sets the speeddata of a speeddata variable in RAPID.
        TODO: update or remove
        """

        resp = self.set_rapid_variable(var, f'[{speeddata},500,5000,1000]')
        if resp.status_code == 204:
            print(f'Set \"{var}\" speeddata to v{speeddata}')
        else:
            print('Could not set speeddata. Check that the variable name is correct')

    """ def send_puck(self, puck_xyz, puck_angle, rotation_z=0, forward_grip=True):
        Sets gripper angle, camera offset and puck target values chosen.
        If collision check, the variable rotation_z and forward grip may be updated
        Keep for reference, gripper_cam_offset removed (unneccessary)
       
        rotation_angle = puck_angle - rotation_z

        self.set_rapid_variable("gripper_angle", rotation_z)
        offset_x, offset_y = gripper_camera_offset(rotation_z)
        if forward_grip:
            self.set_rapid_array("gripper_camera_offset", (offset_x, offset_y))
        else:
            self.set_rapid_array("gripper_camera_offset", (-offset_x, -offset_y))
        self.set_robtarget_translation("puck_target", puck_xyz)
        self.set_rapid_variable("puck_angle", rotation_angle) """