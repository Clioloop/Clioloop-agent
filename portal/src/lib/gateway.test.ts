import { afterEach, describe, expect, it } from "vitest";
import {
  FIRECRAWL_WEB_COST_MICROS,
  GATEWAY_VENDORS,
  gatewayRequestCostMicros,
  gatewayShouldRecordUsage,
  viduRateMicrosPerSecond,
} from "./gateway";
import { PLANS } from "./plans";

const vidu = GATEWAY_VENDORS.vidu;

describe("web (Firecrawl) entitlement", () => {
  it("is gated to Pro and up — free has no web service", () => {
    expect(PLANS.free.services).not.toContain("web");
    expect(PLANS.pro.services).toContain("web");
    expect(PLANS.max.services).toContain("web");
    expect(PLANS.max20x.services).toContain("web");
  });

  it("charges one cent for Firecrawl web search and extract calls", () => {
    expect(GATEWAY_VENDORS.firecrawl.service).toBe("web");
    expect(GATEWAY_VENDORS.firecrawl.costMicros).toBe(10_000);
    expect(FIRECRAWL_WEB_COST_MICROS).toBe(10_000);
    expect(gatewayRequestCostMicros(GATEWAY_VENDORS.firecrawl, "POST", ["v2", "search"])).toBe(10_000);
    expect(gatewayRequestCostMicros(GATEWAY_VENDORS.firecrawl, "POST", ["v2", "scrape"])).toBe(10_000);
    expect(gatewayRequestCostMicros(GATEWAY_VENDORS.firecrawl, "POST", ["extract"])).toBe(10_000);
    expect(gatewayRequestCostMicros(GATEWAY_VENDORS.firecrawl, "GET", ["v2", "search"])).toBe(0);
    expect(gatewayRequestCostMicros(GATEWAY_VENDORS.firecrawl, "POST", ["v2", "map"])).toBe(0);
    // Self-host support: an upstream override env is defined.
    expect(GATEWAY_VENDORS.firecrawl.upstreamEnv).toBe("FIRECRAWL_UPSTREAM_URL");
  });
});

describe("Vidu gateway metering", () => {
  afterEach(() => {
    delete process.env.VIDU_GATEWAY_RATE_540P_MICROS_PER_SECOND;
    delete process.env.VIDU_GATEWAY_RATE_720P_MICROS_PER_SECOND;
    delete process.env.VIDU_GATEWAY_RATE_1080P_MICROS_PER_SECOND;
  });

  it("uses the 20% marked-up per-second rates", () => {
    expect(viduRateMicrosPerSecond("540p")).toBe(42_000);
    expect(viduRateMicrosPerSecond("720p")).toBe(66_000);
    expect(viduRateMicrosPerSecond("1080p")).toBe(78_000);
  });

  it("charges generation requests by duration and resolution", () => {
    expect(
      gatewayRequestCostMicros(
        vidu,
        "POST",
        ["text2video"],
        JSON.stringify({ duration: 10, resolution: "540p" }),
      ),
    ).toBe(420_000);
    expect(
      gatewayRequestCostMicros(
        vidu,
        "POST",
        ["img2video"],
        JSON.stringify({ duration: 3, resolution: "720p" }),
      ),
    ).toBe(198_000);
    expect(
      gatewayRequestCostMicros(
        vidu,
        "POST",
        ["text2video"],
        JSON.stringify({ duration: 2, resolution: "1080p" }),
      ),
    ).toBe(156_000);
  });

  it("defaults to 5s 540p and clamps duration at 10s", () => {
    expect(gatewayRequestCostMicros(vidu, "POST", ["text2video"], "{}")).toBe(210_000);
    expect(
      gatewayRequestCostMicros(
        vidu,
        "POST",
        ["text2video"],
        JSON.stringify({ duration: 999, resolution: "540p" }),
      ),
    ).toBe(420_000);
  });

  it("does not charge polling or non-generation Vidu routes", () => {
    expect(gatewayRequestCostMicros(vidu, "GET", ["tasks", "task-1", "creations"])).toBe(0);
    expect(gatewayRequestCostMicros(vidu, "POST", ["tasks", "task-1", "cancel"])).toBe(0);
  });

  it("allows rate overrides for quick pricing changes", () => {
    process.env.VIDU_GATEWAY_RATE_540P_MICROS_PER_SECOND = "50000";
    expect(viduRateMicrosPerSecond("540p")).toBe(50_000);
    expect(
      gatewayRequestCostMicros(
        vidu,
        "POST",
        ["text2video"],
        JSON.stringify({ duration: 2, resolution: "540p" }),
      ),
    ).toBe(100_000);
  });

  it("records only successful Vidu task creation responses", () => {
    expect(
      gatewayShouldRecordUsage(
        vidu,
        "POST",
        ["text2video"],
        200,
        { task_id: "task-1", state: "created" },
      ),
    ).toBe(true);
    expect(
      gatewayShouldRecordUsage(
        vidu,
        "POST",
        ["text2video"],
        400,
        { error: "bad request" },
      ),
    ).toBe(false);
    expect(
      gatewayShouldRecordUsage(
        vidu,
        "POST",
        ["text2video"],
        200,
        { task_id: "task-1", state: "failed" },
      ),
    ).toBe(false);
    expect(
      gatewayShouldRecordUsage(
        vidu,
        "GET",
        ["tasks", "task-1", "creations"],
        200,
        { state: "success" },
      ),
    ).toBe(false);
  });
});
