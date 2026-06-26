# Platform: DevOps

Cross-platform deployment and infrastructure configuration area. At the moment this workspace includes shared Helm values used by platform services.

## Что здесь лежит

```
devops/
└── ms-helm-values/  # Helm values for microservices and environments
```

## Когда смотреть сюда

- deployment values, environment-specific settings, image tags, ingress, secrets references, or service runtime configuration;
- verifying whether a behavior is controlled by code or by deploy-time values;
- comparing staging/preprod/prod configuration for incident analysis.

## Git

Nested repositories are ignored by the workspace root. Treat this README as the tracked pointer only.
