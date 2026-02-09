"""AXM MCP Server — Runtime execution for the AXM protocol ecosystem."""

from pathlib import Path

from loguru import logger

from axm_mcp._version import __version__

__all__ = ["__version__", "main"]


def main() -> None:
    """Entry point for axm-mcp command."""
    import axm

    from axm.catalog import ResourceCatalog, ResourceInitializer, UpdateStrategy

    from axm_mcp.mcp_app import configure, mcp

    # User workspace (~/axm)
    user_dir = Path.home() / "axm"
    # Package resources are sibling to axm package source
    package_dir = Path(axm.__file__).parent.parent.parent / "resources"

    # Sync resources from package to user workspace (delta sync)
    if user_dir.exists():
        try:
            initializer = ResourceInitializer(user_dir=user_dir, package_dir=package_dir)
            report = initializer.initialize(strategy=UpdateStrategy.UPDATE_NEWER)

            if report.copied:
                logger.info(f"Initialized {len(report.copied)} new resources from package")
            if report.updated:
                logger.info(f"Updated {len(report.updated)} resources from package")
        except Exception as e:
            logger.warning(f"Resource sync failed: {e}")

    catalog = ResourceCatalog(user_dir=user_dir, package_dir=package_dir)
    sessions_path = user_dir / "sessions"
    sessions_path.mkdir(parents=True, exist_ok=True)

    configure(catalog, sessions_path)
    logger.info(f"axm-mcp v{__version__} starting...")
    mcp.run()

