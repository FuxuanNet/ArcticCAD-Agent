/// <reference types="vite/client" />

declare module "*.vue" {
  import type { DefineComponent } from "vue"

  const component: DefineComponent<object, object, unknown>
  export default component
}

declare module "@jscad/stl-serializer" {
  export function serialize(options: Record<string, unknown>, ...objects: unknown[]): unknown[]
}

declare module "@jscad/dxf-serializer" {
  export function serialize(options: Record<string, unknown>, ...objects: unknown[]): unknown[]
}
