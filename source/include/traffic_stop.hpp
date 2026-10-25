#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>

// Portable sequence controller only. This is NOT an SC4 ABI declaration.
// A verified Windows/game-thread adapter is required before use in the game.
namespace speeding {
using Actor = std::uint64_t;
struct StopPlan { Actor offender{}, police{}; float nearby_speed{}, offender_speed{}; };
enum class Stage { idle, chase, siren, pulling_over, fade_in, walking, fade_out, vehicle_fade_out, done, aborted };

class Engine {
public:
    virtual ~Engine() = default;
    // Every nonzero handle returned by prepare() must refer to a newly created,
    // exclusively owned actor. Never return an existing traffic/dispatch actor.
    // Roll back partial allocations before returning false.
    virtual bool prepare(StopPlan&) = 0;
    virtual bool owned_and_alive(Actor) const = 0;
    virtual bool begin_pursuit(Actor police, Actor offender, float speed) = 0;
    // Disabling must succeed even if the police actor has already disappeared.
    virtual bool set_siren(Actor police, bool enabled) = 0;
    // Reserve a valid shoulder pair, respecting road side, direction and terrain.
    // Apply native pull-over behavior only to the two specified owned actors.
    virtual bool request_safe_stop(Actor offender, Actor police) = 0;
    virtual bool both_stopped(Actor offender, Actor police) const = 0;
    // Spawn at the stopped police car with opacity ZERO before first rendering.
    virtual Actor spawn_officer(Actor police) = 0;
    virtual bool opacity(Actor officer, float alpha) = 0;
    // Resolve the driver's actual side; route from officer to that side safely.
    virtual bool walk_to_driver(Actor officer, Actor offender) = 0;
    virtual bool at_driver(Actor officer, Actor offender) const = 0;
    // Allocate a mod-owned incident in the native crime map; retain its token.
    // Partial failure must leave no incident. No existing incident is repurposed.
    virtual bool report_speeding(Actor offender, std::uint64_t& token) = 0;
    virtual void retire_incident(std::uint64_t token) = 0;
    // Release only this adapter's handles; invalidated city-generation handles
    // must be harmless. Engine Remove(bool) semantics remain to be verified.
    virtual void remove_owned(Actor) = 0;
};

struct Timing {
    double chase_seconds=2, siren_seconds=4, stop_deadline=12;
    double fade_in_seconds=1, walk_deadline=12, visit_seconds=2, fade_out_seconds=1, vehicle_fade_out_seconds=1.5;
};

class TrafficStop {
    Engine& e;
    Timing t;
    StopPlan p{};
    Actor officer{};
    std::uint64_t incident{};
    bool has_incident=false, siren_on=false, arrived=false;
    Stage state=Stage::idle;
    double elapsed=0, visit_elapsed=0;
    void enter(Stage next) { state=next; elapsed=0; }
    void release(Stage end) {
        if (siren_on) e.set_siren(p.police,false);
        siren_on=false;
        if (officer) e.remove_owned(officer);
        if (p.police) e.remove_owned(p.police);
        if (p.offender) e.remove_owned(p.offender);
        if (has_incident) e.retire_incident(incident);
        p={}; officer=0; incident=0; has_incident=false; enter(end);
    }
    bool pair_alive() const {
        return e.owned_and_alive(p.offender) && e.owned_and_alive(p.police);
    }
    static bool positive(double n) { return std::isfinite(n) && n>0; }
public:
    explicit TrafficStop(Engine& engine, Timing timing={}) : e(engine),t(timing) {}
    TrafficStop(const TrafficStop&)=delete;
    TrafficStop& operator=(const TrafficStop&)=delete;
    Stage stage() const { return state; }
    bool start() {
        if (state!=Stage::idle && state!=Stage::done && state!=Stage::aborted) return false;
        if (!positive(t.chase_seconds) || !positive(t.siren_seconds) ||
            !positive(t.stop_deadline) || !positive(t.fade_in_seconds) ||
            !positive(t.walk_deadline) || !positive(t.visit_seconds) || !positive(t.fade_out_seconds) || !positive(t.vehicle_fade_out_seconds)) return false;
        p={}; arrived=false; visit_elapsed=0;
        if (!e.prepare(p)) { p={}; enter(Stage::aborted); return false; }
        if (!p.offender || !p.police || p.offender==p.police || !pair_alive() ||
            !std::isfinite(p.nearby_speed) || p.nearby_speed<0 ||
            !std::isfinite(p.offender_speed) || p.offender_speed<=p.nearby_speed) {
            release(Stage::aborted); return false;
        }
        if (!e.begin_pursuit(p.police,p.offender,p.offender_speed)) { release(Stage::aborted); return false; }
        if (!e.report_speeding(p.offender,incident)) { release(Stage::aborted); return false; }
        has_incident=true; enter(Stage::chase); return true;
    }
    // Call on the verified game update thread. dt is simulation-active real-time
    // seconds, NOT calendar time. The adapter supplies zero while paused.
    // One transition per tick keeps phases ordered even after a long stall.
    void tick(double dt) {
        if (state==Stage::idle || state==Stage::done || state==Stage::aborted) return;
        if (!pair_alive() || (officer && !e.owned_and_alive(officer))) { release(Stage::aborted); return; }
        if (!std::isfinite(dt) || dt<=0) return;
        elapsed+=dt;
        switch(state) {
        case Stage::chase:
            if (elapsed>=t.chase_seconds) {
                if (!e.set_siren(p.police,true)) { release(Stage::aborted); return; }
                siren_on=true; enter(Stage::siren);
            } break;
        case Stage::siren:
            if (elapsed>=t.siren_seconds) {
                if (!e.request_safe_stop(p.offender,p.police)) { release(Stage::aborted); return; }
                enter(Stage::pulling_over);
            } break;
        case Stage::pulling_over:
            if (e.both_stopped(p.offender,p.police)) {
                officer=e.spawn_officer(p.police);
                if (!officer || !e.owned_and_alive(officer) || !e.opacity(officer,0)) { release(Stage::aborted); return; }
                enter(Stage::fade_in);
            } else if (elapsed>=t.stop_deadline) release(Stage::aborted);
            break;
        case Stage::fade_in:
            if (!e.opacity(officer,static_cast<float>(std::min(1.0,elapsed/t.fade_in_seconds)))) { release(Stage::aborted); return; }
            if (elapsed>=t.fade_in_seconds) {
                if (!e.walk_to_driver(officer,p.offender)) { release(Stage::aborted); return; }
                enter(Stage::walking);
            } break;
        case Stage::walking:
            if (!arrived && e.at_driver(officer,p.offender)) { arrived=true; visit_elapsed=0; }
            else if (arrived) visit_elapsed+=dt;
            if (arrived && visit_elapsed>=t.visit_seconds) enter(Stage::fade_out);
            else if (!arrived && elapsed>=t.walk_deadline) release(Stage::aborted);
            break;
        case Stage::fade_out:
            if (!e.opacity(officer,static_cast<float>(std::max(0.0,1.0-elapsed/t.fade_out_seconds)))) { release(Stage::aborted); return; }
            if (elapsed>=t.fade_out_seconds) { e.remove_owned(officer);officer=0;enter(Stage::vehicle_fade_out); }
            break;
        case Stage::vehicle_fade_out: {
            float alpha=static_cast<float>(std::max(0.0,1.0-elapsed/t.vehicle_fade_out_seconds));
            if (!e.opacity(p.offender,alpha) || !e.opacity(p.police,alpha)) { release(Stage::aborted);return; }
            if (elapsed>=t.vehicle_fade_out_seconds) release(Stage::done);
        }
            break;
        default: break;
        }
    }
    // Must be called BEFORE the city/engine services become invalid.
    void cancel() { if (state!=Stage::idle && state!=Stage::done && state!=Stage::aborted) release(Stage::aborted); }
};
}
