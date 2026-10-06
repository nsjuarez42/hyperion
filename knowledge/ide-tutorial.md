# HyperAI IDE

The HyperAI IDE is the integrated development environment of the HYPER-AI project. It is used to build, run, and inspect AI workflows. The public IDE is at https://ide.hyperai.di.uoa.gr/ and the tutorial is at https://ide-tutorial.hyperai.di.uoa.gr/.

HYPER-AI aims to redefine data processing with distributed computing swarms: autonomous networks of interconnected nodes that adapt and optimise resources across the cloud, edge, and IoT continuum. It uses semantic representation and autonomic behaviour: self-configuring, self-healing, and self-optimising.

Users describe workloads as application profiles. A native application is a YAML document whose root is `applicationProfile`. It describes a container or VM workload: metadata, runtime (image, entry point, base OS), resources, network, constraints, and QoS. A device application is a Kubernetes-style manifest with `apiVersion: hyper.ai/v1` and `kind: Application`. It deploys an Android APK, a Docker image, or an ESP32 binary onto a DeviceNode. A third profile type, integration, is for composing multi-component services.

The IDE checks these files against the native-app and device-app rules. Hyperion can create, edit, read, validate, and delete them.
