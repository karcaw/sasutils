#
# Copyright (C) 2016, 2017
#      The Board of Trustees of the Leland Stanford Junior University
# Written by Stephane Thiell <sthiell@stanford.edu>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Build a useful udev alias from a SAS (array) block device.

The alias is built from the associated enclosure nickname (must be set)
and the array device bay identifier.

Example of udev rule:

KERNEL=="sd*", PROGRAM="/usr/bin/sas_sd_snic_alias %k", SYMLINK+="%c"
"""

from __future__ import print_function
import logging
import sys

from sasutils.sas import SASBlockDevice
from sasutils.scsi import EnclosureDevice
from sasutils.ses import ses_get_snic_nickname
from sasutils.sysfs import sysfs

ALIAS_FORMAT = '{nickname}-bay{bay_identifier:02d}'


def sas_sd_snic_alias(blkdev):
    """Use sasutils library to get the alias name from the block device."""

    # NOTE: Unfortunately, we cannot always rely on sysfs block device
    # 'enclosure_device' symlink to the array device (at least not on
    # 3.10.0-327.36.3.el7). We have to do the enclosure lookup ourselves
    # as a workaround.

    # Preload enclosure dict (sas_address -> EnclosureDevice)
    enclosures = {}
    for encl in sysfs.node('class').node('enclosure'):
        encldev = EnclosureDevice(encl.node('device'))
        enclosures[encldev.attrs.sas_address] = encldev

    # Instantiate SASBlockDevice object from block device sysfs node
    #   eg. /sys/block/sdx/device
    blkdev = SASBlockDevice(sysfs.node('block').node(blkdev.rstrip('0123456789')).node('device'))
    sasdev = blkdev.end_device.sas_device

    if blkdev.array_device:
        # 'enclosure_device' symlink is present (preferred method)
        # Use array_device and enclosure to retrieve the ses sg name
        ses_sg = blkdev.array_device.enclosure.scsi_generic.sg_name
    else:
        # 'enclosure_device' symlink is absent: use workaround (see NOTE)
        try:
            encl = enclosures[sasdev.attrs.enclosure_identifier]
            ses_sg = encl.scsi_generic.sg_name
        except KeyError:
            # not an array device
            logging.warning('%s not an array device (%s)', blkdev.name,
                            blkdev.sysfsnode.path)
            raise

    # Retrieve bay_identifier from matching sas_device
    bay = int(sasdev.attrs.bay_identifier)

    # Get subenclosure nickname
    snic = ses_get_snic_nickname(ses_sg) or '%s_no_snic' % blkdev.name

    return ALIAS_FORMAT.format(nickname=snic, bay_identifier=bay)


def main():
    """Entry point for sas_sd_snic_alias command-line."""
    if len(sys.argv) != 2:
        print('Usage: %s <blkdev>' % sys.argv[0], file=sys.stderr)
        sys.exit(1)
    try:
        result = sas_sd_snic_alias(sys.argv[1])
        if result:
            print(result)
    except KeyError as err:
        print("Not found: {0}".format(err), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
