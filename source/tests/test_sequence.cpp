#include "../include/traffic_stop.hpp"
#include <cassert>
#include <limits>
#include <set>
#include <string>
#include <vector>
#include <iostream>
using namespace speeding;
struct Fake final: Engine {
    std::set<Actor> actors;
    std::vector<std::string> events;
    bool stopped=false, reached=false, fail_report=false;
    float speed=55, alpha=-1;
    bool prepare(StopPlan& p) override { actors={101,102,999}; p={101,102,35,speed}; return true; }
    bool owned_and_alive(Actor a) const override { return a!=999 && actors.count(a); }
    bool begin_pursuit(Actor a,Actor b,float v) override { assert(a==102 && b==101 && v==speed); events.push_back("pursuit");return true; }
    bool set_siren(Actor,bool on) override { events.push_back(on?"siren_on":"siren_off");return true; }
    bool request_safe_stop(Actor a,Actor b) override { assert(a==101 && b==102);events.push_back("stop");return true; }
    bool both_stopped(Actor,Actor) const override { return stopped; }
    Actor spawn_officer(Actor) override { actors.insert(103);events.push_back("officer");return 103; }
    bool opacity(Actor,float a) override { assert(a>=0 && a<=1);alpha=a;return true; }
    bool walk_to_driver(Actor,Actor) override { events.push_back("walk");return true; }
    bool at_driver(Actor,Actor) const override { return reached; }
    bool report_speeding(Actor,std::uint64_t& token) override { if(fail_report)return false;token=77;events.push_back("crime");return true; }
    void retire_incident(std::uint64_t token) override { assert(token==77);events.push_back("retire"); }
    void remove_owned(Actor a) override { assert(a==101 || a==102 || a==103);actors.erase(a);events.push_back("remove"); }
};
void enter_stop(TrafficStop& s) { assert(s.start());s.tick(2);assert(s.stage()==Stage::siren);s.tick(3);assert(s.stage()==Stage::siren);s.tick(1);assert(s.stage()==Stage::pulling_over); }
int main() {
    {
        Fake f;TrafficStop s(f);enter_stop(s);
        s.tick(1);assert(!f.actors.count(103));
        f.stopped=true;s.tick(.1);assert(s.stage()==Stage::fade_in && f.alpha==0);
        s.tick(.5);assert(f.alpha==.5f);s.tick(.5);assert(s.stage()==Stage::walking);
        s.tick(1);assert(s.stage()==Stage::walking);
        f.reached=true;s.tick(.1);s.tick(2);assert(s.stage()==Stage::fade_out);
        s.tick(.5);assert(f.alpha==.5f);s.tick(.5);
        assert(s.stage()==Stage::vehicle_fade_out && !f.actors.count(103));
        s.tick(.75);assert(f.alpha==.5f && f.actors.count(101) && f.actors.count(102));s.tick(.75);
        assert(s.stage()==Stage::done && f.alpha==0 && f.actors==std::set<Actor>{999});
        auto count=f.events.size();s.tick(100);s.cancel();assert(count==f.events.size());
        assert(f.events[0]=="pursuit" && f.events[1]=="crime" && f.events[2]=="siren_on" && f.events[3]=="stop");
    }
    {
        Fake f;TrafficStop s(f);assert(s.start());s.tick(0);s.tick(-1);s.tick(std::numeric_limits<double>::quiet_NaN());assert(s.stage()==Stage::chase);
        f.actors.erase(101);s.tick(0);assert(s.stage()==Stage::aborted && f.actors==std::set<Actor>{999});
    }
    { Fake f;TrafficStop s(f);enter_stop(s);s.tick(12);assert(s.stage()==Stage::aborted && !f.actors.count(103)); }
    { Fake f;f.speed=35;TrafficStop s(f);assert(!s.start() && f.actors==std::set<Actor>{999}); }
    { Fake f;f.fail_report=true;TrafficStop s(f);assert(!s.start() && f.actors==std::set<Actor>{999}); }
    { Fake f;TrafficStop s(f);assert(s.start());s.cancel();auto n=f.events.size();s.cancel();assert(f.events.size()==n && f.actors==std::set<Actor>{999}); }
    { Fake f;TrafficStop s(f);assert(s.start());s.tick(2);f.actors.erase(102);s.tick(.1);assert(s.stage()==Stage::aborted);assert(std::find(f.events.begin(),f.events.end(),"siren_off")!=f.events.end()); }
    std::cout<<"7 sequence scenarios passed; no game integration tested\n";
}
