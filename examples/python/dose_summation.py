#!/usr/bin/env python
"""
Dose simulation.

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

PATIENT_ID = 'hyperarc'


def main(args):
    """
    Execution of example source code

    Input argument args contains patient id and Velocity app type.
    If not assigned from console then values from script are used.

    """
    e = create_engine(args.app)  # creation of velocity engine instance

    patient = e.loadPatientByPatientId(args.patient_id)
    regOps = e.getRegistrationOperations()
    volOps = e.getVolumeOperations()
    orThrow(patient, e=e)
    print('Loaded patient: {}'.format(args.patient_id))

    # sort CTs by AcquisitionDate
    cts = list(patient.getVolumes('CT'))
    cts.sort(key=lambda x: x.getAcquisitionDate())
    doses = list(patient.getVolumes('RTDOSE'))

    # find all CT-DS in the same frame of reference
    # if multiple DS for same CT pick first one that has a plan
    print('-- Finding CT-DS pairs to be resampled --')
    ctDosePair = {}
    for ct in cts:
        plans = list(ct.getLinkedPlans())
        for d in doses:
            if d.getName() == 'auto resampled' or d.getName() == 'Sum RTDOSE':
                continue
            if ct.getFrameOfReferenceUID() == d.getFrameOfReferenceUID():
                ctDosePair[ct] = d
                if next((p for p in plans if p.getInstanceUID() == d.getPlanUID()), None) is not None:
                    break

    # resample doses onto the most recent CT
    print('-- Resampling DS onto most recent CT --')
    primaryCT = cts[-1]  # most recent by Acq Date
    resampledDoses = []
    primaryDoseId = -1

    for ct in ctDosePair:
        dose = ctDosePair.get(ct)
        if ct.getVelocityId() != primaryCT.getVelocityId():
            # need to load CT-DS to activate/create DICOM registration needed for chain
            orThrow(e.loadPrimaryVolume(ct.getVelocityId()), e=e)
            print('Loaded CT {} as primary volume'.format(ct.getName()))
            orThrow(e.loadSecondaryVolume(dose.getVelocityId()), e=e)
            print('Loaded Dose {} as secondary volume'.format(dose.getName()))
            dicomReg = e.loadRegistrationByName('DICOM')
            orThrow(dicomReg, e=e)

            # make new reg for resampling between primary CT and secondary CT
            ct2ctReg = makeAutoReg(primaryCT, ct, 'resample_reg', e=e, regOps=regOps)

            # now load primary CT and dose, load chain reg and resample onto primary CT
            orThrow(e.loadPrimaryVolume(primaryCT.getVelocityId()), e=e)
            print('Loaded CT {} as primary volume'.format(primaryCT.getName()))
            orThrow(e.loadSecondaryVolume(dose.getVelocityId()), e=e)
            print('Loaded Dose id {} as secondary volume'.format(dose.getName()))
            # load registration resample_reg + DICOM
            orThrow(e.loadChainRegistration(ct2ctReg.getVelocityId(), dicomReg.getVelocityId()), e=e)
            print('Loaded registration: {}'.format('resample_reg + DICOM'))
            print('Creating resampled dose...')
            id = volOps.createResampledVolume(velocity.VolumeResampleReplace, "auto resampled")
            if id == -1:
                print('Error creating resampled dose ' + volOps.getErrorMessage())
                continue
            print('Resampled dose created with id {}'.format(id))
            resampledDoses.append(id)
        else:
            # this dose does not require resample, same FOR as primary CT
            primaryDoseId = dose.getVelocityId()
            resampledDoses.append(primaryDoseId)

    print('Summing {} dose volumes ...'.format(len(resampledDoses)))
    orThrow(e.loadPrimaryVolume(primaryDoseId), e=e)  # load primary dose as anchor
    print('Loaded DS id {} as primary volume'. format(primaryDoseId))
    sumId = volOps.createResampledVolumeAggregate(
        velocity.VolumeResampleAdd, resampledDoses, velocity.ResampleFlags.AllowNone  # sum
    )
    if sumId == -1:
        print('Error creating sum dose ' + volOps.getErrorMessage())
    else:
        print('Sum dose created with id {}'.format(sumId))


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


def makeAutoReg(pVol, sVol, regName, e, regOps):
    orThrow(e.loadPrimaryVolume(pVol.getVelocityId()), e=e)
    print('Loaded {} as primary volume'.format(pVol.getName()))
    orThrow(e.loadSecondaryVolume(sVol.getVelocityId()), e=e)
    print('Loaded {} as secondary volume'.format(sVol.getName()))
    print('Creating registration object: {}'.format(regName))
    registration = regOps.createNewRegistration(regName)
    orThrow(registration, regOps)
    orThrow(e.loadRegistration(registration.getVelocityId()), e=e)
    # now run rigid registration
    print('Running rigid registration...')
    regSettings = velocity.DefaultRigidRegistrationSettings()
    orThrow(regOps.performRigidRegistrationDICOM(regSettings), regOps)
    print('reg done.')
    orThrow(regOps.saveRegistration(), regOps)
    return registration


if __name__ == "__main__":
    args = parse_arguments()
    main(args)
