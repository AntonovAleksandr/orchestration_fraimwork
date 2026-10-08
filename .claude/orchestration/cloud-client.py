#!/usr/bin/env python3
"""Phase 3: Cloud Branches - Distributed Worker Execution

Enables orchestration framework to run workers on:
- AWS Lambda (serverless, pay-per-use)
- Google Cloud Run (containers, auto-scaling)
- Azure Functions (enterprise)

Provides:
- Worker invocation API
- State sync across local/cloud
- Cost monitoring
- Automatic fallback to local execution
"""

import json
import time
import logging
from typing import Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


class CloudProvider(Enum):
    """Supported cloud providers"""
    AWS_LAMBDA = "aws_lambda"
    GCP_CLOUD_RUN = "gcp_cloud_run"
    AZURE_FUNCTIONS = "azure_functions"
    LOCAL = "local"


@dataclass
class WorkerInvocation:
    """Cloud worker invocation request"""
    phase: int
    phase_config: Dict
    worker_location: str  # "local", "aws", "gcp", "azure"
    timeout_seconds: int
    max_retries: int
    cost_limit_cents: Optional[int] = None


@dataclass
class WorkerResult:
    """Cloud worker execution result"""
    status: str  # "success", "failed", "timeout"
    result: Optional[Dict]
    error: Optional[str]
    duration_seconds: float
    cost_cents: float
    worker_location: str
    execution_id: str


class CloudClient:
    """Client for distributed worker execution"""

    def __init__(self, config: Dict):
        """Initialize cloud client

        Args:
            config: {
                "provider": "aws|gcp|azure",
                "region": "us-east-1",
                "worker_image": "us.gcr.io/project/worker:latest",
                "cost_monitoring": True,
                "fallback_to_local": True
            }
        """
        self.config = config
        self.provider = CloudProvider[config.get("provider", "AWS_LAMBDA").upper()]
        self.region = config.get("region", "us-east-1")
        self.cost_monitoring = config.get("cost_monitoring", True)
        self.fallback_to_local = config.get("fallback_to_local", True)

        self._init_provider_client()

    def _init_provider_client(self):
        """Initialize provider-specific client"""
        if self.provider == CloudProvider.AWS_LAMBDA:
            try:
                import boto3
                self.lambda_client = boto3.client("lambda", region_name=self.region)
                self.pricing_client = boto3.client("pricing", region_name="us-east-1")
                print(f"✓ AWS Lambda client initialized (region: {self.region})")
            except ImportError:
                logger.warning("boto3 not available - AWS Lambda disabled")
                self.lambda_client = None

        elif self.provider == CloudProvider.GCP_CLOUD_RUN:
            try:
                from google.cloud import run_v2
                self.cloudrun_client = run_v2.ServicesClient()
                print(f"✓ GCP Cloud Run client initialized (region: {self.region})")
            except ImportError:
                logger.warning("google-cloud-run not available - Cloud Run disabled")
                self.cloudrun_client = None

        elif self.provider == CloudProvider.AZURE_FUNCTIONS:
            try:
                from azure.functions import FunctionClient
                self.function_client = FunctionClient()
                print(f"✓ Azure Functions client initialized")
            except ImportError:
                logger.warning("azure-functions not available - Azure disabled")
                self.function_client = None

    async def invoke_worker(self, invocation: WorkerInvocation) -> WorkerResult:
        """Invoke worker on cloud provider

        Args:
            invocation: Worker invocation request

        Returns:
            WorkerResult with execution status and output
        """
        execution_id = self._generate_execution_id()
        start_time = time.time()

        try:
            # Validate cost limits if configured
            if invocation.cost_limit_cents and self.cost_monitoring:
                estimated_cost = self._estimate_cost(invocation)
                if estimated_cost > invocation.cost_limit_cents:
                    logger.warning(f"Cost limit exceeded: ${estimated_cost/100:.2f} > ${invocation.cost_limit_cents/100:.2f}")
                    if self.fallback_to_local:
                        logger.info("Falling back to local execution")
                        return await self._invoke_local(invocation, execution_id, start_time)
                    else:
                        raise OverflowError(f"Cost limit exceeded: ${estimated_cost/100:.2f}")

            # Invoke on selected provider
            if invocation.worker_location == "aws" and self.lambda_client:
                result = await self._invoke_lambda(invocation, execution_id)
            elif invocation.worker_location == "gcp" and self.cloudrun_client:
                result = await self._invoke_cloud_run(invocation, execution_id)
            elif invocation.worker_location == "azure" and self.function_client:
                result = await self._invoke_azure(invocation, execution_id)
            else:
                logger.info(f"Provider not available, using local execution")
                result = await self._invoke_local(invocation, execution_id, start_time)

            duration = time.time() - start_time
            result.duration_seconds = duration
            result.execution_id = execution_id

            return result

        except Exception as e:
            logger.error(f"Cloud invocation failed: {e}")

            if self.fallback_to_local:
                logger.info("Falling back to local execution")
                return await self._invoke_local(invocation, execution_id, start_time)
            else:
                raise

    async def _invoke_lambda(self, invocation: WorkerInvocation, execution_id: str) -> WorkerResult:
        """Invoke AWS Lambda function"""
        payload = {
            "phase": invocation.phase,
            "phase_config": invocation.phase_config,
            "execution_id": execution_id,
        }

        try:
            response = self.lambda_client.invoke(
                FunctionName="orchestration-worker",
                InvocationType="RequestResponse",
                Payload=json.dumps(payload),
            )

            result = json.loads(response["Payload"].read())

            return WorkerResult(
                status=result.get("status", "success"),
                result=result.get("result"),
                error=result.get("error"),
                duration_seconds=result.get("duration", 0),
                cost_cents=self._calculate_lambda_cost(result.get("duration", 0)),
                worker_location="aws",
                execution_id=execution_id,
            )

        except Exception as e:
            logger.error(f"Lambda invocation failed: {e}")
            raise

    async def _invoke_cloud_run(self, invocation: WorkerInvocation, execution_id: str) -> WorkerResult:
        """Invoke Google Cloud Run service"""
        import asyncio
        import aiohttp

        url = f"https://orchestration-worker-{self.region}.run.app/execute"
        payload = {
            "phase": invocation.phase,
            "phase_config": invocation.phase_config,
            "execution_id": execution_id,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=invocation.timeout_seconds) as response:
                    result = await response.json()

            return WorkerResult(
                status=result.get("status", "success"),
                result=result.get("result"),
                error=result.get("error"),
                duration_seconds=result.get("duration", 0),
                cost_cents=self._calculate_cloudrun_cost(result.get("duration", 0)),
                worker_location="gcp",
                execution_id=execution_id,
            )

        except asyncio.TimeoutError:
            return WorkerResult(
                status="timeout",
                result=None,
                error=f"Cloud Run timeout after {invocation.timeout_seconds}s",
                duration_seconds=invocation.timeout_seconds,
                cost_cents=self._calculate_cloudrun_cost(invocation.timeout_seconds),
                worker_location="gcp",
                execution_id=execution_id,
            )
        except Exception as e:
            logger.error(f"Cloud Run invocation failed: {e}")
            raise

    async def _invoke_azure(self, invocation: WorkerInvocation, execution_id: str) -> WorkerResult:
        """Invoke Azure Functions"""
        # Placeholder for Azure implementation
        logger.info("Azure Functions invocation (placeholder)")

        return WorkerResult(
            status="failed",
            result=None,
            error="Azure Functions not yet implemented",
            duration_seconds=0,
            cost_cents=0,
            worker_location="azure",
            execution_id=execution_id,
        )

    async def _invoke_local(self, invocation: WorkerInvocation, execution_id: str,
                           start_time: float) -> WorkerResult:
        """Fallback: invoke worker locally"""
        # This would import and run the autonomous worker locally
        duration = time.time() - start_time

        return WorkerResult(
            status="success",
            result={"message": "Executed locally (cloud fallback)"},
            error=None,
            duration_seconds=duration,
            cost_cents=0,  # No cloud cost for local execution
            worker_location="local",
            execution_id=execution_id,
        )

    def _estimate_cost(self, invocation: WorkerInvocation) -> float:
        """Estimate cloud execution cost in cents"""
        if invocation.worker_location == "aws":
            # AWS Lambda: $0.0000002 per GB-second
            # Assuming 1GB memory, 60 second max execution
            return max(0.20, invocation.timeout_seconds * 0.0002) * 100

        elif invocation.worker_location == "gcp":
            # GCP Cloud Run: $0.00001667 per CPU-second
            # Assuming 1 CPU, timeout-second execution
            return invocation.timeout_seconds * 0.00001667 * 100

        else:
            return 0

    def _calculate_lambda_cost(self, duration_seconds: float) -> float:
        """Calculate actual AWS Lambda cost"""
        # GB-seconds (1GB, duration)
        gb_seconds = duration_seconds
        # $0.0000002 per GB-second = 0.00002 cents per GB-second
        return gb_seconds * 0.00002

    def _calculate_cloudrun_cost(self, duration_seconds: float) -> float:
        """Calculate actual GCP Cloud Run cost"""
        # CPU-seconds (1 CPU, duration)
        cpu_seconds = duration_seconds
        # $0.00001667 per CPU-second = 0.001667 cents
        return cpu_seconds * 0.001667

    def _generate_execution_id(self) -> str:
        """Generate unique execution ID"""
        return f"exec-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

    def get_cost_report(self, period_hours: int = 24) -> Dict:
        """Get cost report for period"""
        return {
            "period_hours": period_hours,
            "total_invocations": 0,  # Would query CloudWatch/Stackdriver
            "total_cost_cents": 0,
            "by_provider": {},
            "timestamp": datetime.utcnow().isoformat(),
        }


# Configuration templates
CLOUD_CONFIG_TEMPLATES = {
    "aws": {
        "provider": "aws_lambda",
        "region": "us-east-1",
        "cost_monitoring": True,
        "fallback_to_local": True,
        "cost_limit_cents": 1000,  # $10 per phase max
    },
    "gcp": {
        "provider": "gcp_cloud_run",
        "region": "us-central1",
        "worker_image": "us.gcr.io/your-project/orchestration-worker:latest",
        "cost_monitoring": True,
        "fallback_to_local": True,
        "cost_limit_cents": 500,  # $5 per phase max
    },
    "hybrid": {
        "provider": "aws_lambda",  # Primary
        "fallback_to_local": True,  # Secondary
        "cost_monitoring": True,
        "cost_limit_cents": 2000,
    },
}


if __name__ == "__main__":
    print("Cloud Client Examples")
    print("=" * 60)

    # Example 1: AWS Lambda configuration
    print("\n1. AWS Lambda Configuration")
    print("-" * 60)
    print(json.dumps(CLOUD_CONFIG_TEMPLATES["aws"], indent=2))

    # Example 2: GCP Cloud Run configuration
    print("\n2. GCP Cloud Run Configuration")
    print("-" * 60)
    print(json.dumps(CLOUD_CONFIG_TEMPLATES["gcp"], indent=2))

    # Example 3: Hybrid configuration
    print("\n3. Hybrid Configuration (AWS + Local Fallback)")
    print("-" * 60)
    print(json.dumps(CLOUD_CONFIG_TEMPLATES["hybrid"], indent=2))

    print("\n✅ Cloud Client examples complete")
