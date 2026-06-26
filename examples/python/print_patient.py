#!/usr/bin/env python
"""
Prints out all information and data on the patient.

REQUIRES:
- created user of type Script in Velocity
- suitable patient data already imported in Velocity

Can be run in 2 different ways - for GRID or WORKSTATION.
This is specified using --app input argument.

"""
import velocity
import argparse
import atexit

APP_TYPE = "grid"  # grid or workstation (can be overriden from console e.g. --app_type workstation)
DB_PATH = r"/Velocity/Databases/vscDatabase"  # will be used only if app == workstation
DB_NAME = "vscDatabase"                       # will be used only if app == grid
DB_USER = "script"
DB_PASS = "script"
DB_IP   = "127.0.0.1"
DB_PORT = 57000

# assumes "sixCBCT, AdaptiveMonitoring" patient loaded by default
PATIENT_ID = 'AW3Y6TA684'  # can be overriden from console e.g. --patient_id xyz


def main(args):
    """
    Execution of example source code

    Input argument args contains patient id and Velocity app type.
    If not assigned from console then values from script are used.

    """
    e = create_engine(args.app)  # creation of velocity engine instance

    pops = e.getPatientDataOperations()
    patient = pops.getPatientByPatientId(args.patient_id)
    orThrow(patient, pops)
    print_object(patient, 'patient')


def parse_arguments():
    """
    This method enables usege of console input arguments for PATIENT_ID and APP_TYPE.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--app",
        type=str.lower,
        choices=["grid", "workstation"],
        default=APP_TYPE,
        help="Application type [grid/workstation]"
    )
    parser.add_argument(
        "--patient_id",
        type=str,
        default=PATIENT_ID,
        help="Database user. User needs to be created in Velocity before running script. User type has to be Script."
    )
    args = parser.parse_args()
    print(f"Starting example with APP TYPE = {args.app} and PATIENT ID = {args.patient_id}")
    return args


def orThrow(c, e):
    if not c or (hasattr(c, 'isValid') and not c.isValid()):
        raise RuntimeError(e.getErrorMessage())


def create_engine(app_type):
    """
    Creates the Velocity engine client and login. After that we can load
    patients and volumes using engine as if it was a client.

    """
    e = velocity.VelocityEngine()
    if app_type.lower() == "workstation":
        orThrow(e.loginToWorkstation(DB_USER, DB_PASS, DB_PATH, True), e)
    elif app_type.lower() == "grid":
        orThrow(e.loginToGrid(DB_USER, DB_PASS, DB_IP, DB_PORT, DB_NAME), e)
    else:
        raise ValueError(f"Unknown application type {app_type}. Choose either grid/workstation")
    atexit.register(e.logout)  # ensure we log out when the script ends
    return e


def compare_key(obj_and_name):
    """
    Compare objects for printing. We consider wrapped lists (having size())
    to come after anything else, otherwise sort by name.
    """
    obj, obj_name = obj_and_name
    return (hasattr(obj, 'size'), obj_name)


def print_object(obj, obj_name, indent=0, seen_ids=None):
    """
    Recursively prints an object.
    @param obj       the object to print
    @param obj_name  the object name used when printing
    @param indent    indentation level, for internal use
    @param seen_ids  infinite recursion prevention, for internal use

    """
    pre = '-' * indent
    if seen_ids is None:
        seen_ids = set()
    # for std::vector wrappers
    if hasattr(obj, 'size'):
        # print the name, then each child, e.g. 'obj', then 'obj[0]', 'obj[1]', etc
        print('{}{} [{} elements]:'.format(pre, obj_name, obj.size()))
        for i, child in enumerate(obj):
            child_name = obj_name + '[' + str(i) + ']'
            print_object(child, child_name, indent + 1, seen_ids)
    # for non-API types
    elif not hasattr(obj, 'this'):
        # print the name and value
        print('{}{}: {}'.format(pre, obj_name, obj))
    # for all other API types
    else:
        # prevent infinite loop by checking for already seen objects
        seen_id = (repr(type(obj)), obj.getVelocityId())
        if seen_id in seen_ids:
            print('{}{}: {}'.format(pre, obj_name, "[ALREADY SEEN]"))
        else:
            # remember that we saw this one
            seen_ids.add(seen_id)
            # get all the data inspection functions and call them
            try:
                children = [
                    (getattr(obj, attr)(), attr)
                    for attr in dir(obj)
                    if (attr.startswith('get') or attr.startswith('is')) and attr not in ('this', 'getRecord')
                ]
                # sort to get primitives before child lists
                children.sort(key=compare_key)
                # now recurse to all the children
                for child, attr in children:
                    child_name = obj_name + '.' + attr + '()'
                    print_object(child, child_name, indent + 1, seen_ids)
            except Exception as err:
                print("Problem with object: {} (attrs={})".format(obj, dir(obj)))
                print(f"An error occurred: {err}")


if __name__ == "__main__":
    args = parse_arguments()
    main(args)
