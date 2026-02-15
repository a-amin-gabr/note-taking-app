#!/bin/bash
# =====================================================
# Step 6: Prepare EBS Backup Volume
# Formats, mounts, and persists an EBS volume as /backup
# Usage: Called by deploy.sh or run standalone:
#   sudo ./06_prepare_volume.sh [device]
# =====================================================

DEVICE="${1:-/dev/nvme1n1}"
MOUNT_POINT="/backup"
FS_TYPE="xfs"
TARGET_USER="ec2-user"

echo "========================================="
echo "Step 6: Preparing Backup Volume"
echo "========================================="

# Verify device exists
if [ ! -b "$DEVICE" ]; then
    echo "[ERROR] Device $DEVICE not found!"
    echo "Available block devices:"
    lsblk
    exit 1
fi

# Check if already mounted
CURRENT_MOUNT=$(findmnt -n -o TARGET "$DEVICE" 2>/dev/null)
if [ -n "$CURRENT_MOUNT" ]; then
    if [ "$CURRENT_MOUNT" == "$MOUNT_POINT" ]; then
        echo "Volume already mounted at $MOUNT_POINT. Skipping."
        exit 0
    fi
    echo "[ERROR] Device is mounted at $CURRENT_MOUNT. Unmount first."
    exit 1
fi

# Format if no filesystem
EXISTING_FS=$(blkid -o value -s TYPE "$DEVICE" 2>/dev/null)
if [ -z "$EXISTING_FS" ]; then
    echo "Formatting $DEVICE with $FS_TYPE..."
    mkfs -t "$FS_TYPE" "$DEVICE"
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to format $DEVICE"
        exit 1
    fi
else
    echo "Existing filesystem: $EXISTING_FS (skipping format)"
fi

# Create mount point and mount
mkdir -p "$MOUNT_POINT"
mount "$DEVICE" "$MOUNT_POINT"
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to mount $DEVICE"
    exit 1
fi

# Set ownership
if id "$TARGET_USER" &>/dev/null; then
    chown "$TARGET_USER:$TARGET_USER" "$MOUNT_POINT"
fi

# Persist in fstab
if grep -q "$MOUNT_POINT" /etc/fstab; then
    echo "fstab entry already exists."
else
    UUID=$(blkid -o value -s UUID "$DEVICE")
    if [ -n "$UUID" ]; then
        echo "UUID=$UUID $MOUNT_POINT $FS_TYPE defaults,nofail 0 2" >> /etc/fstab
        echo "Added fstab entry (UUID=$UUID)"
    else
        echo "$DEVICE $MOUNT_POINT $FS_TYPE defaults,nofail 0 2" >> /etc/fstab
        echo "Added fstab entry ($DEVICE)"
    fi
fi

echo "[OK] Backup volume mounted at $MOUNT_POINT"
echo "   Size: $(df -h "$MOUNT_POINT" | awk 'NR==2{print $2}')"
