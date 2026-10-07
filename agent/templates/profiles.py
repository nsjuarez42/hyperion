"""YAML templates the IDE validator accepts.

Placeholders are {name}-style and filled with str.replace (see render.fill),
not str.format, so the literal { value: 1, unit: "W" } maps stay intact.
Use single braces only.
"""

NATIVE_TEMPLATE = """applicationProfile:
  metadata:
    type: "native"
    schemaVersion: "1.1.0"
    name: "{name}"
    version: "1.0.0"
    description: "{description}"
    owner: "hyperion"
    lifecyclePhase: "development"
  specs:
    runtime:
      executionType: "container"
      entryPoint: "{entry}"
      args: {args}
      baseOS:
        name: "debian"
        version: "12"
      containerImage:
        uri: "{image}"
        tag: "{tag}"
    resources:
      cpu: "100m"
      memory: "128Mi"
      storage: "1Gi"
    network:
      ports:
        - port: {port}
          protocol: "TCP"
    constraints:
      supportedArchitectures: ["amd64"]
"""

DEVICE_TAIL = """
  network:
    ports:
      - port: {port}
        protocol: "HTTP"
    networkBandwidthMin: { value: 1, unit: "Mbps" }
  qos:
    latencyToleranceMax: { value: 500, unit: "ms" }
    energyCost: { value: 1, unit: "W" }
    monetaryCost: { value: 0.01, currency: "USD", per: "hour" }
    resilience: "auto-restart"
    availability: { value: 0.9, unit: "fraction" }
    startupTime: { value: 5, unit: "s" }
  constraints:
    schedulingPriority: 1
    supportedArchitectures: ["amd64", "arm64"]
    geoLocationRequirement: "LocalZone"
    isHighlyAvailable: false
    faultTolerance: "graceful-degradation"
    dataClassification: "internal"
"""

DEVICE_DOCKER = (
    """apiVersion: hyper.ai/v1
kind: Application
metadata:
  name: {name}
  annotations:
    intent: "{description}"
spec:
  app:
    type: device
    schemaVersion: "1.0.0"
    name: "{name}"
    version: "1.0.0"
    description: "{description}"
    owner: "hyperion"
    lifecyclePhase: "development"
  workload:
    kind: DockerImage
    dockerImage:
      image: "{image_ref}"
      imagePullPolicy: "IfNotPresent"
"""
    + DEVICE_TAIL
)

DEVICE_ANDROID = (
    """apiVersion: hyper.ai/v1
kind: Application
metadata:
  name: {name}
  annotations:
    intent: "{description}"
spec:
  app:
    type: device
    schemaVersion: "1.0.0"
    name: "{name}"
    version: "1.0.0"
    description: "{description}"
    owner: "hyperion"
    lifecyclePhase: "development"
  workload:
    kind: AndroidApk
    androidApk:
      apkUrl: "{apk_url}"
      packageName: "{package}"
      installMode: "install"
"""
    + DEVICE_TAIL
)

DEVICE_ESP32 = (
    """apiVersion: hyper.ai/v1
kind: Application
metadata:
  name: {name}
  annotations:
    intent: "{description}"
spec:
  app:
    type: device
    schemaVersion: "1.0.0"
    name: "{name}"
    version: "1.0.0"
    description: "{description}"
    owner: "hyperion"
    lifecyclePhase: "development"
  workload:
    kind: esp32Binary
    esp32Binary:
      binaryUrl: "{binary_url}"
      chip: {chip}
      flash:
        method: {flash_method}
"""
    + DEVICE_TAIL
)
