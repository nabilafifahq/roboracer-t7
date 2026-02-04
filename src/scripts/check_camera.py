import depthai as dai

try:
    with dai.Device() as device:
        # Get Technical Details
        eeprom = device.readCalibration().getEepromData()
        print(f"\n=== CAMERA CONNECTED ===")
        print(f"Product Name: {eeprom.productName}")
        print(f"Board Name:   {eeprom.boardName}")
        
        # Check for Sensors
        features = device.getConnectedCameraFeatures()
        print(f"\n=== SENSORS FOUND ===")
        for cam in features:
            print(f" - Socket {cam.socket}: {cam.sensorName} ({cam.width}x{cam.height})")

except Exception as e:
    print("\n[ERROR] No OAK-D Camera found!")
    print("1. Is it plugged in?")
    print("2. Did you run Docker with --privileged?")
    print(f"Error details: {e}")