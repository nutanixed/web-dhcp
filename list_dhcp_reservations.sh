#!/bin/bash

# Configuration
LEASE_FILE="/var/lib/misc/dnsmasq.leases"
RESERVATION_FILE="/etc/dnsmasq.d/dhcp_reservations.conf"
PASS="nutanix/4u"

usage() {
    echo "Usage: $0 {list|add|del|update} [MAC] [IP]"
    echo "  list - Show current DHCP leases and reservations"
    echo "  add  - Create a static DHCP reservation for a MAC address and IP"
    echo "  del  - Remove a static DHCP reservation by MAC address"
    echo "  update - Update a static DHCP reservation for a MAC address"
    exit 1
}

list_reservations() {
    echo "Active DHCP Leases (from $LEASE_FILE):"
    echo "--------------------------------------------------------------------------------"
    printf "%-20s %-15s %-15s %-20s\n" "MAC Address" "IP Address" "Hostname" "Expiry Time"
    echo "--------------------------------------------------------------------------------"

    if [ -f "$LEASE_FILE" ]; then
        while read -r expiry mac ip hostname clientid; do
            if [[ "$expiry" =~ ^[0-9]+$ ]]; then
                expiry_date=$(date -d "@$expiry" "+%Y-%m-%d %H:%M:%S")
            else
                expiry_date="Static/Unknown"
            fi
            printf "%-20s %-15s %-15s %-20s\n" "$mac" "$ip" "$hostname" "$expiry_date"
        done < "$LEASE_FILE"
    else
        echo "No active leases found."
    fi

    echo ""
    echo "Static DHCP Reservations (from $RESERVATION_FILE):"
    echo "--------------------------------------------------------------------------------"
    printf "%-20s %-15s\n" "MAC Address" "IP Address"
    echo "--------------------------------------------------------------------------------"
    
    if [ -f "$RESERVATION_FILE" ] || echo "$PASS" | sudo -S [ -f "$RESERVATION_FILE" ]; then
        echo "$PASS" | sudo -S cat "$RESERVATION_FILE" 2>/dev/null | grep "dhcp-host=" | while read -r line; do
            # Extract mac and ip from dhcp-host=mac,ip
            content=${line#*=}
            mac=${content%,*}
            ip=${content#*,}
            printf "%-20s %-15s\n" "$mac" "$ip"
        done
    else
        echo "No static reservations found."
    fi
}

add_reservation() {
    local mac=$1
    local ip=$2
    
    if [ -z "$mac" ] || [ -z "$ip" ]; then
        usage
    fi

    echo "Adding DHCP reservation: $mac -> $ip"
    echo "$PASS" | sudo -S bash -c "echo 'dhcp-host=$mac,$ip' >> $RESERVATION_FILE"
    
    echo "Restarting dnsmasq service..."
    echo "$PASS" | sudo -S systemctl restart dnsmasq
    echo "Reservation added and dnsmasq restarted."
}

del_reservation() {
    local mac=$1
    
    if [ -z "$mac" ]; then
        usage
    fi

    echo "Deleting DHCP reservation for MAC: $mac"
    echo "$PASS" | sudo -S sed -i "/dhcp-host=$mac,/d" "$RESERVATION_FILE"
    
    echo "Restarting dnsmasq service..."
    echo "$PASS" | sudo -S systemctl restart dnsmasq
    echo "Reservation for $mac removed and dnsmasq restarted."
}

update_reservation() {
    local mac=$1
    local ip=$2
    
    if [ -z "$mac" ] || [ -z "$ip" ]; then
        usage
    fi

    echo "Updating DHCP reservation for MAC: $mac to IP: $ip"
    echo "$PASS" | sudo -S sed -i "s/dhcp-host=$mac,.*/dhcp-host=$mac,$ip/" "$RESERVATION_FILE"
    
    echo "Restarting dnsmasq service..."
    echo "$PASS" | sudo -S systemctl restart dnsmasq
    echo "Reservation for $mac updated to $ip and dnsmasq restarted."
}

ACTION=$1

case "$ACTION" in
    list)
        list_reservations
        ;;
    add)
        add_reservation "$2" "$3"
        ;;
    del)
        del_reservation "$2"
        ;;
    update)
        update_reservation "$2" "$3"
        ;;
    *)
        if [ -z "$ACTION" ]; then
            list_reservations
        else
            usage
        fi
        ;;
esac
