import type { ApiGateway } from "./contracts"
import { remoteGateway } from "./remoteGateway"

export type { AgentGateway, ApiGateway, ProjectGateway } from "./contracts"
export const apiGateway: ApiGateway = remoteGateway
