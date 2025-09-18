import hashlib
import os
import re
import sys
import logging
import yaml

from dataclasses import dataclass, field
from domino import Domino
from pathlib import Path
from typing import Any, List, Dict, Optional, Union
from urllib.parse import urlparse, urlunparse


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("domino-environment-automation")

@dataclass
class ProxyConfig:
    port: int
    internalPath: Optional[str] = None
    requireSubdomain: Optional[bool] = False
    rewrite: Optional[bool] = False


@dataclass
class WorkspaceTool:
    title: str
    iconUrl: str
    startScripts: List[str]
    supportedFileExtensions: Optional[List[str]] = field(default_factory=list)
    proxyConfig: Optional[ProxyConfig] = None


class EnvironmentConfig:
    def __init__(
        self,
        environment_config_location,
        environment_id: str = "",
        dockerfile_instructions: str = "",
        environment_variables: List[Dict[str, Any]] = None,
        base_image: str = "",
        post_run_script: str = "",
        post_setup_script: str = "",
        pre_run_script: str = "",
        pre_setup_script: str = "",
        skip_cache: bool = False,
        summary: str = "",
        supported_clusters: List[str] = None,
        tags: List[str] = None,
        use_vpn: bool = False,
        workspace_tools: List[Dict[str, Any]] = None,
        add_base_dependencies: bool = True,
        description : Union[str, List[str]] = None,
        is_restricted: bool = True,
        name: str = "",
        organization_owner_id: str = "",
        visibility: str = "Private",
        config_file_hash : str = ""
    ):

        self.environment_config_location = environment_config_location
        self.environment_id = environment_id
        self.dockerfile_instructions = dockerfile_instructions
        self.environment_variables = environment_variables or []
        self.base_image = base_image
        self.post_run_script = post_run_script
        self.post_setup_script = post_setup_script
        self.pre_run_script = pre_run_script
        self.pre_setup_script = pre_setup_script
        self.skip_cache = skip_cache
        self.summary = summary
        self.supported_clusters = supported_clusters or []
        self.tags = tags or []
        self.use_vpn = use_vpn
        self.workspace_tools = workspace_tools or []
        self.add_base_dependencies = add_base_dependencies
        self.description = description
        self.is_restricted = is_restricted
        self.name = name
        self.organization_owner_id = organization_owner_id
        self.visibility = visibility
        self.config_file_hash = config_file_hash


    def get_environment_visibility(self):
        with open(self.environment_config_location, 'r') as environment_config:
            config = yaml.safe_load(environment_config)

        possible_visibility_types = ["Global", "Organization", "Private"]

        self.visibility = config.get("visibility").title() if config.get("visibility") else "Private"

        if self.visibility.upper() == "Organisation":
            self.visibility = "Organization"

        if self.visibility == "Organization" and not config.get("organizationOwnerId"):
            logger.error("Please provide the ID of an Organization that will own this environment")
            return
        elif config.get("organizationOwnerId"):
            self.organization_owner_id = config.get("organizationOwnerId")
            if not re.search("^[0-9a-fA-F]{24}$", self.organization_owner_id):
                logger.error(f"Organization Owner ID {self.organization_owner_id} not recognised.")
                return
            else:
                self.visibility = "Private"

        if self.visibility not in possible_visibility_types:
            logger.warning(f"Invalid Visibility setting in {self.environment_config_location} – setting to PRIVATE")
            self.visibility = "Private"


    def get_supported_clusters(self):
        with open(self.environment_config_location, 'r') as environment_config:
            config = yaml.safe_load(environment_config)

        possible_cluster_types = ["Spark", "Ray", "Dask", "Mpi"]

        self.supported_clusters = config.get("supportedClusters") if config.get("supportedClusters") else []
        # Normalize case to Title for comparison (e.g., "spark" -> "Spark")
        self.supported_clusters = [str(sc).title() for sc in self.supported_clusters]

        if self.supported_clusters:
            invalid_values = [sc for sc in self.supported_clusters if sc not in possible_cluster_types]
            if invalid_values:
                logger.warning(f"Invalid Cluster Type setting {invalid_values} – choose 'Spark', 'Ray', 'Dask', or 'Mpi'")
                self.supported_clusters = [sc for sc in self.supported_clusters if sc in possible_cluster_types]


    def build_workspace_tools(self):
        with open(self.environment_config_location, 'r') as environment_config:
            config = yaml.safe_load(environment_config)
            pwts = config.get("pluggableWorkspaceTools", {})
            self.workspace_tools = []

            for name, pwt_config in pwts.items():
                proxy_config = pwt_config.get("httpProxy")
                http_proxy = ProxyConfig(**proxy_config) if proxy_config else None

                wt = WorkspaceTool(
                    title = pwt_config["title"],
                    iconUrl= pwt_config["iconUrl"],
                    startScripts=pwt_config["start"],
                    supportedFileExtensions=pwt_config.get("supportedFileExtensions",[]),
                    proxyConfig = http_proxy,
                )

                workspace_tools_dict = {
                    "iconUrl": wt.iconUrl if wt.iconUrl else "",
                    "name": name,
                    "proxyConfig": {
                        "internalPath": wt.proxyConfig.internalPath if wt.proxyConfig and wt.proxyConfig.internalPath else "",
                        "port": wt.proxyConfig.port if wt.proxyConfig and wt.proxyConfig.port else "",
                        "requireSubdomain": wt.proxyConfig.requireSubdomain if wt.proxyConfig and wt.proxyConfig.requireSubdomain else False,
                        "rewrite": wt.proxyConfig.rewrite if wt.proxyConfig and wt.proxyConfig.rewrite else False
                    },
                    "startScripts": wt.startScripts,
                    "supportedFileExtensions": wt.supportedFileExtensions,
                    "title": wt.title if wt.title else name
                }
                self.workspace_tools.append(workspace_tools_dict)


    def check_environment_exists(self):
        existing_environments = domino.environments_list()
        for ee in existing_environments['data']:
            if ee["name"] == self.name:
                self.environment_id = ee["id"]
                return True
        return None


    def compute_config_file_hash(self, algorithm='sha256'):
        """Compute the hash of a file using the specified algorithm."""
        hash_func = hashlib.new(algorithm)

        with open(self.environment_config_location, 'rb') as file:
            # Read the file in chunks of 8192 bytes
            while chunk := file.read(8192):
                hash_func.update(chunk)

        self.config_file_hash = hash_func.hexdigest()


    def parse_config_file(self):
        with open(self.environment_config_location, 'r') as environment_config:
            config = yaml.safe_load(environment_config)

        self.name                           = config.get("name") if config.get("name") else ""
        self.base_image                     = config.get("image") if config.get("image") else ""
        self.dockerfile_instructions        = config.get("dockerfileInstructions") if config.get("dockerfileInstructions") else ""
        self.environment_variables          = config.get("environmentVariables") if config.get("environmentVariables") else []
        self.pre_setup_script               = config.get("preSetupScript") if config.get("preSetupScript") else ""
        self.post_setup_script              = config.get("postSetupScript") if config.get("postSetupScript") else ""
        self.pre_run_script                 = config.get("preRunScript") if config.get("preRunScript") else ""
        self.post_run_script                = config.get("postRunScript") if config.get("postRunScript") else ""
        self.skip_cache                     = config.get("skipCache") if config.get("skipCache") else False
        self.summary                        = config.get("summary") if config.get("summary") else ""
        self.tags                           = config.get("tags") if config.get("tags") else []
        self.use_vpn                        = config.get("useVpn") if config.get("useVpn") else False
        self.description                    = config.get("description") if config.get("description") else ""
        self.is_restricted                  = config.get("isRestricted") if config.get("isRestricted") else False
        self.organization_owner_id          = config.get("organizationOwnerId") if config.get("organizationOwnerId") else ""

        self.get_environment_visibility()
        self.get_supported_clusters()
        self.build_workspace_tools()

        self.compute_config_file_hash()
        self.tags.append(self.config_file_hash)


    def create_environment(self):
        self.parse_config_file()

        domino.create_environment(
            name                            = self.name,
            visibility                      = self.visibility,
            dockerfile_instructions         = self.dockerfile_instructions,
            environment_variables           = self.environment_variables,
            base_image                      = self.base_image,
            post_run_script                 = self.post_run_script,
            post_setup_script               = self.post_setup_script,
            pre_run_script                  = self.pre_run_script,
            pre_setup_script                = self.pre_setup_script,
            skip_cache                      = self.skip_cache,
            summary                         = self.summary,
            supported_clusters              = self.supported_clusters,
            tags                            = self.tags,
            use_vpn                         = self.use_vpn,
            workspace_tools                 = self.workspace_tools,
            add_base_dependencies           = self.add_base_dependencies,
            description                     = self.description,
            is_restricted                   = self.is_restricted,
            organization_owner_id           = self.organization_owner_id
        )

        self.check_environment_exists()


    def create_environment_if_not_exist(self):
        if not self.name:
            logger.error("Environment requires a name.")
            return False
        else:
            self.check_environment_exists()

        if self.environment_id:
            logger.info(f"Environment {self.name} already exists. {self.environment_id}")
            return True
        else:
            logger.info(f"Environment {self.name} doesn't already exist.")
            self.create_environment()
            return True


    def get_latest_revision(self):
        environment_spec = domino.get_environment(self.environment_id)
        active_revision_tags = environment_spec["environment"].get("activeRevisionTags") or []
        tag_match = self.config_file_hash in active_revision_tags
        return tag_match


    def create_environment_revision(self):
        file_unchanged = self.get_latest_revision()
        if file_unchanged:
           logger.info("File has not changed since last run")
        else:
            domino.create_environment_revision(
                environment_id          = self.environment_id,
                dockerfile_instructions = self.dockerfile_instructions,
                environment_variables   = self.environment_variables,
                base_image              = self.base_image,
                post_run_script         = self.post_run_script,
                post_setup_script       = self.post_setup_script,
                pre_run_script          = self.pre_run_script,
                pre_setup_script        = self.pre_setup_script,
                skip_cache              = self.skip_cache,
                summary                 = self.summary,
                supported_clusters      = self.supported_clusters,
                tags                    = self.tags,
                use_vpn                 = self.use_vpn,
                workspace_tools         = self.workspace_tools
            )
            self.restrict_environment_revision()


    def restrict_environment_revision(self):
        get_environment = domino.get_environment(self.environment_id)
        restricted_revision = get_environment["environment"].get('restrictedRevision') or None
        selected_revision = get_environment["environment"].get('selectedRevision') or None
        if selected_revision:
            selected_revision_id = selected_revision["id"]
            logger.debug(selected_revision_id)
            if not restricted_revision and self.is_restricted == True:
                logger.debug("Restricting selected revision as environment is marked restricted")
                domino.restrict_environment_revision(self.environment_id, selected_revision_id)


    def archive_environment(self):
        domino.archive_environment(self.environment_id)


def get_domino_host():
    host = os.getenv("DOMINO_URL")
    if not host:
        logger.error("Please provide an environment variable DOMINO_URL with the URL of your Domino instance.")
        sys.exit(1)
    parsed = urlparse(host if "://" in host else f"https://{host}")
    parsed = parsed._replace(scheme="https")
    host = urlunparse(parsed)
    if not host.endswith("/"):
        host += "/"
    logger.info(f"Connecting to {host}")
    return host


def get_target_directory():
    target_directory = os.getenv("TARGET_DIRECTORY")
    if not target_directory:
        cwd_candidate = os.path.join(Path(os.getcwd()).absolute(), "environment_templates")
        parent_candidate = os.path.join(Path(os.getcwd()).parent.absolute(), "environment_templates")
        if os.path.isdir(cwd_candidate):
            target_directory = cwd_candidate
        elif os.path.isdir(parent_candidate):
            target_directory = parent_candidate
        else:
            logger.error("Could not find 'environment_templates' in current or parent directory. Set TARGET_DIRECTORY or create the folder.")
            sys.exit(1)
    elif not target_directory.endswith("/environment_templates"):
        if target_directory.endswith("/"):
            target_directory = os.path.join(target_directory, "environment_templates")
        else:
            target_directory = os.path.join(target_directory + "/environment_templates")
    if not os.path.isdir(target_directory):
        logger.error(f"Target directory does not exist: {target_directory}")
        sys.exit(1)
    logger.info(f"Target directory: {target_directory}")
    return target_directory


def process_single_environment(environment, target_directory):
    environment_config_location = Path(os.path.join(target_directory, environment, "environment.yaml"))
    if not environment_config_location.exists():
        logger.warning(f"No configuration file found for {environment}– skipping")
        return
    try:
        ec = EnvironmentConfig(environment_config_location=environment_config_location)
        ec.parse_config_file()
        ec.create_environment_if_not_exist()
        ec.create_environment_revision()
        ec.restrict_environment_revision()
    except Exception as e:
        logger.error(f"Failed to process environment '{environment}': {e}")
        return


def process_all_environments(target_directory):
    local_environments_list = os.listdir(target_directory)
    if not local_environments_list:
        logger.error("No environments found to build!")
        sys.exit(1)
    logger.info(f"Building environments: {local_environments_list}")
    for environment in local_environments_list:
        process_single_environment(environment, target_directory)
    sys.exit(0)


def main():
    global domino
    if all(k in os.environ for k in ("DOMINO_PROJECT_OWNER", "DOMINO_PROJECT_NAME")):
        domino_project = f"{os.environ['DOMINO_PROJECT_OWNER']}/{os.environ['DOMINO_PROJECT_NAME']}"
    else:
        logger.error("Please provide environment variables DOMINO_PROJECT_OWNER and DOMINO_PROJECT_NAME.")
        sys.exit(1)

    if os.getenv("DOMINO_API_PROXY"):
        domino = Domino(domino_project)
    else:
        host = get_domino_host()
        api_key = os.getenv("DOMINO_API_KEY")
        auth_token = os.getenv("DOMINO_AUTH_TOKEN")
        if not api_key and not auth_token:
            logger.error("Please provide an environment variable DOMINO_API_KEY with your Domino API key, or DOMINO_AUTH_TOKEN with a Service Account token.")
            sys.exit(1)
        domino = Domino(domino_project, api_key=api_key, host=host, auth_token=auth_token)
    
    target_directory = get_target_directory()
    process_all_environments(target_directory)


if __name__ == "__main__":
    main()
