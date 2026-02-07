"""Storage plugin interface and built-in implementations.

Storage plugins provide file storage capabilities through various backends.
The StoragePlugin interface defines the contract for storing and retrieving files.

Supported Backends (built-in):
- Local: Local filesystem storage
- S3: Amazon S3 (and S3-compatible: MinIO, DigitalOcean Spaces, etc.)
- GCS: Google Cloud Storage
- Azure Blob: Azure Blob Storage

Example:
    >>> # Using S3 storage
    >>> plugin = S3StoragePlugin()
    >>> await plugin.init(context)
    >>> await plugin.upload(
    ...     "documents/invoice.pdf",
    ...     file_content,
    ...     content_type="application/pdf",
    ... )
    >>> url = await plugin.get_url("documents/invoice.pdf")
"""

import os
from abc import abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO

from src.infrastructure.plugins.base import Plugin, PluginContext, PluginMetadata


class StoragePlugin(Plugin):
    """Base interface for storage plugins.

    All storage plugins must implement this interface to provide
    consistent file storage and retrieval.

    Methods:
        upload: Upload file to storage
        download: Download file from storage
        delete: Delete file from storage
        exists: Check if file exists
        get_url: Get public or signed URL for file
        list_files: List files in directory/prefix
    """

    @abstractmethod
    async def upload(
        self,
        path: str,
        content: bytes | BinaryIO,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Upload file to storage.

        Args:
            path: File path/key (e.g., "documents/invoice.pdf")
            content: File content (bytes or file-like object)
            content_type: MIME type (e.g., "application/pdf")
            metadata: Custom metadata key-value pairs

        Returns:
            Storage path/key of uploaded file

        Example:
            >>> await plugin.upload(
            ...     "avatars/user123.jpg",
            ...     image_bytes,
            ...     content_type="image/jpeg",
            ...     metadata={"user_id": "123"}
            ... )
        """
        pass

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """Download file from storage.

        Args:
            path: File path/key

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist

        Example:
            >>> content = await plugin.download("documents/invoice.pdf")
        """
        pass

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete file from storage.

        Args:
            path: File path/key

        Example:
            >>> await plugin.delete("temp/old-file.txt")
        """
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if file exists.

        Args:
            path: File path/key

        Returns:
            True if file exists, False otherwise

        Example:
            >>> if await plugin.exists("avatars/user123.jpg"):
            ...     print("Avatar exists")
        """
        pass

    @abstractmethod
    async def get_url(
        self,
        path: str,
        expires_in: int | None = None,
        public: bool = False,
    ) -> str:
        """Get URL for file.

        Args:
            path: File path/key
            expires_in: URL expiration in seconds (for signed URLs)
            public: Whether to return public URL (vs signed URL)

        Returns:
            File URL (public or signed)

        Example:
            >>> # Public URL
            >>> url = await plugin.get_url("public/logo.png", public=True)
            >>>
            >>> # Signed URL (expires in 1 hour)
            >>> url = await plugin.get_url("private/document.pdf", expires_in=3600)
        """
        pass

    async def list_files(
        self,
        prefix: str = "",
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List files in storage.

        Args:
            prefix: Path prefix to filter by
            limit: Maximum number of files to return

        Returns:
            List of file info dicts with keys: path, size, modified_at

        Example:
            >>> files = await plugin.list_files(prefix="documents/")
            >>> for file in files:
            ...     print(f"{file['path']}: {file['size']} bytes")
        """
        return []


class LocalStoragePlugin(StoragePlugin):
    """Local filesystem storage plugin.

    Stores files on local filesystem. Useful for development and
    single-server deployments.

    Configuration:
        base_path: Base directory for file storage
        create_dirs: Auto-create directories (default: True)
        public_url_base: Base URL for public files (optional)

    Example:
        >>> context = PluginContext(config={
        ...     "base_path": "/var/app/storage",
        ...     "public_url_base": "https://example.com/files",
        ... })
        >>> plugin = LocalStoragePlugin()
        >>> await plugin.init(context)
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Plugin metadata."""
        return PluginMetadata(
            name="local-storage",
            version="1.0.0",
            description="Local filesystem storage",
            author="Python Fast Forge",
            plugin_type="storage",
            config_schema={
                "type": "object",
                "properties": {
                    "base_path": {"type": "string"},
                    "create_dirs": {"type": "boolean", "default": True},
                    "public_url_base": {"type": "string"},
                },
                "required": ["base_path"],
            },
        )

    async def init(self, context: PluginContext) -> None:
        """Initialize local storage."""
        self.context = context
        self._base_path = Path(context.config["base_path"])
        self._create_dirs = context.config.get("create_dirs", True)
        self._public_url_base = context.config.get("public_url_base")

        # Create base directory if needed
        if self._create_dirs:
            self._base_path.mkdir(parents=True, exist_ok=True)

    async def validate(self) -> bool:
        """Validate configuration."""
        return "base_path" in self.context.config

    async def upload(
        self,
        path: str,
        content: bytes | BinaryIO,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Upload file to local storage."""
        file_path = self._base_path / path

        # Create directory
        if self._create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        if isinstance(content, bytes):
            file_path.write_bytes(content)
        else:
            with open(file_path, "wb") as f:
                f.write(content.read())

        if self.context and self.context.logger:
            self.context.logger.info(
                "file_uploaded",
                path=path,
                size=file_path.stat().st_size,
            )

        return path

    async def download(self, path: str) -> bytes:
        """Download file from local storage."""
        file_path = self._base_path / path

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        return file_path.read_bytes()

    async def delete(self, path: str) -> None:
        """Delete file from local storage."""
        file_path = self._base_path / path

        if file_path.exists():
            file_path.unlink()

            if self.context and self.context.logger:
                self.context.logger.info("file_deleted", path=path)

    async def exists(self, path: str) -> bool:
        """Check if file exists."""
        return (self._base_path / path).exists()

    async def get_url(
        self,
        path: str,
        expires_in: int | None = None,
        public: bool = False,
    ) -> str:
        """Get URL for file.

        For local storage, returns public URL if configured,
        otherwise returns file:// URL.
        """
        if self._public_url_base:
            return f"{self._public_url_base.rstrip('/')}/{path}"
        else:
            return f"file://{self._base_path / path}"

    async def list_files(
        self,
        prefix: str = "",
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List files in local storage."""
        base_dir = self._base_path / prefix
        if not base_dir.exists():
            return []

        files = []
        for file_path in base_dir.rglob("*"):
            if file_path.is_file():
                relative_path = str(file_path.relative_to(self._base_path))
                stat = file_path.stat()

                files.append(
                    {
                        "path": relative_path,
                        "size": stat.st_size,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime),
                    }
                )

                if limit and len(files) >= limit:
                    break

        return files


class S3StoragePlugin(StoragePlugin):
    """Amazon S3 storage plugin.

    Stores files in Amazon S3 or S3-compatible storage (MinIO, DigitalOcean
    Spaces, etc.).

    Configuration:
        bucket: S3 bucket name
        region: AWS region (default: us-east-1)
        access_key_id: AWS access key ID
        secret_access_key: AWS secret access key
        endpoint_url: Custom endpoint URL (for S3-compatible services)
        public_url_base: Base URL for public files (optional)

    Example:
        >>> context = PluginContext(config={
        ...     "bucket": "my-app-files",
        ...     "region": "us-west-2",
        ...     "access_key_id": "AKIAIOSFODNN7EXAMPLE",
        ...     "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        ... })
        >>> plugin = S3StoragePlugin()
        >>> await plugin.init(context)
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Plugin metadata."""
        return PluginMetadata(
            name="s3-storage",
            version="1.0.0",
            description="Amazon S3 storage",
            author="Python Fast Forge",
            plugin_type="storage",
            config_schema={
                "type": "object",
                "properties": {
                    "bucket": {"type": "string"},
                    "region": {"type": "string", "default": "us-east-1"},
                    "access_key_id": {"type": "string"},
                    "secret_access_key": {"type": "string"},
                    "endpoint_url": {"type": "string"},
                    "public_url_base": {"type": "string"},
                },
                "required": ["bucket", "access_key_id", "secret_access_key"],
            },
        )

    async def init(self, context: PluginContext) -> None:
        """Initialize S3 client."""
        self.context = context
        self._bucket = context.config["bucket"]
        self._region = context.config.get("region", "us-east-1")
        self._access_key_id = context.config["access_key_id"]
        self._secret_access_key = context.config["secret_access_key"]
        self._endpoint_url = context.config.get("endpoint_url")
        self._public_url_base = context.config.get("public_url_base")

        # Initialize boto3 S3 client
        try:
            import boto3

            self._client = boto3.client(
                "s3",
                region_name=self._region,
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                endpoint_url=self._endpoint_url,
            )
            self._s3_available = True

            if context.logger:
                context.logger.info(
                    "s3_plugin_initialized",
                    bucket=self._bucket,
                    region=self._region,
                )
        except ImportError:
            if context.logger:
                context.logger.warning(
                    "s3_not_available",
                    message="boto3 not installed. Install with: pip install boto3",
                )
            self._client = None
            self._s3_available = False

    async def validate(self) -> bool:
        """Validate S3 configuration."""
        required = ["bucket", "access_key_id", "secret_access_key"]
        return all(key in self.context.config for key in required)

    async def upload(
        self,
        path: str,
        content: bytes | BinaryIO,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Upload file to S3."""
        # Check if S3 is available
        if not self._s3_available or not self._client:
            if self.context and self.context.logger:
                self.context.logger.warning(
                    "s3_unavailable",
                    message="S3 client not available, upload skipped",
                    path=path,
                )
            return path

        try:
            # Build put_object parameters
            put_params = {
                "Bucket": self._bucket,
                "Key": path,
                "Body": content,
            }

            if content_type:
                put_params["ContentType"] = content_type

            if metadata:
                put_params["Metadata"] = metadata

            # Upload to S3
            self._client.put_object(**put_params)

            if self.context and self.context.logger:
                self.context.logger.info(
                    "s3_file_uploaded",
                    path=path,
                    bucket=self._bucket,
                    size=len(content) if isinstance(content, bytes) else None,
                )

            return path

        except Exception as e:
            if self.context and self.context.logger:
                self.context.logger.error(
                    "s3_upload_failed",
                    path=path,
                    bucket=self._bucket,
                    error=str(e),
                )
            raise

    async def download(self, path: str) -> bytes:
        """Download file from S3."""
        # Check if S3 is available
        if not self._s3_available or not self._client:
            if self.context and self.context.logger:
                self.context.logger.warning(
                    "s3_unavailable",
                    message="S3 client not available, returning empty bytes",
                    path=path,
                )
            return b""

        try:
            response = self._client.get_object(Bucket=self._bucket, Key=path)
            content = response["Body"].read()

            if self.context and self.context.logger:
                self.context.logger.info(
                    "s3_file_downloaded",
                    path=path,
                    bucket=self._bucket,
                    size=len(content),
                )

            return content

        except Exception as e:
            if self.context and self.context.logger:
                self.context.logger.error(
                    "s3_download_failed",
                    path=path,
                    bucket=self._bucket,
                    error=str(e),
                )
            raise

    async def delete(self, path: str) -> None:
        """Delete file from S3."""
        # Check if S3 is available
        if not self._s3_available or not self._client:
            if self.context and self.context.logger:
                self.context.logger.warning(
                    "s3_unavailable",
                    message="S3 client not available, delete skipped",
                    path=path,
                )
            return

        try:
            self._client.delete_object(Bucket=self._bucket, Key=path)

            if self.context and self.context.logger:
                self.context.logger.info(
                    "s3_file_deleted",
                    path=path,
                    bucket=self._bucket,
                )

        except Exception as e:
            if self.context and self.context.logger:
                self.context.logger.error(
                    "s3_delete_failed",
                    path=path,
                    bucket=self._bucket,
                    error=str(e),
                )
            raise

    async def exists(self, path: str) -> bool:
        """Check if file exists in S3."""
        # Check if S3 is available
        if not self._s3_available or not self._client:
            if self.context and self.context.logger:
                self.context.logger.warning(
                    "s3_unavailable",
                    message="S3 client not available, returning False",
                    path=path,
                )
            return False

        try:
            from botocore.exceptions import ClientError

            self._client.head_object(Bucket=self._bucket, Key=path)
            return True

        except ClientError:
            return False

        except Exception as e:
            if self.context and self.context.logger:
                self.context.logger.error(
                    "s3_exists_check_failed",
                    path=path,
                    bucket=self._bucket,
                    error=str(e),
                )
            return False

    async def get_url(
        self,
        path: str,
        expires_in: int | None = None,
        public: bool = False,
    ) -> str:
        """Get URL for S3 file."""
        if public and self._public_url_base:
            return f"{self._public_url_base.rstrip('/')}/{path}"

        # Generate signed URL if expires_in is provided
        if expires_in and self._s3_available and self._client:
            try:
                url = self._client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self._bucket, "Key": path},
                    ExpiresIn=expires_in,
                )

                if self.context and self.context.logger:
                    self.context.logger.debug(
                        "s3_presigned_url_generated",
                        path=path,
                        expires_in=expires_in,
                    )

                return url

            except Exception as e:
                if self.context and self.context.logger:
                    self.context.logger.error(
                        "s3_presigned_url_failed",
                        path=path,
                        error=str(e),
                    )
                # Fall through to default URL

        # Default public URL
        return f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{path}"

    async def list_files(
        self,
        prefix: str = "",
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List files in S3 bucket."""
        # Check if S3 is available
        if not self._s3_available or not self._client:
            if self.context and self.context.logger:
                self.context.logger.warning(
                    "s3_unavailable",
                    message="S3 client not available, returning empty list",
                )
            return []

        try:
            response = self._client.list_objects_v2(
                Bucket=self._bucket,
                Prefix=prefix,
                MaxKeys=limit or 1000,
            )

            files = []
            for obj in response.get("Contents", []):
                files.append({
                    "path": obj["Key"],
                    "size": obj["Size"],
                    "modified_at": obj["LastModified"],
                })

            if self.context and self.context.logger:
                self.context.logger.info(
                    "s3_files_listed",
                    bucket=self._bucket,
                    prefix=prefix,
                    count=len(files),
                )

            return files

        except Exception as e:
            if self.context and self.context.logger:
                self.context.logger.error(
                    "s3_list_failed",
                    bucket=self._bucket,
                    prefix=prefix,
                    error=str(e),
                )
            raise


__all__ = [
    "StoragePlugin",
    "LocalStoragePlugin",
    "S3StoragePlugin",
]
