// SC4Speeding: experimental native integration, built against the supplied EXE.
// See README for verification limits and supported executable signatures.
#include "include/win_api.hpp"
#include "include/traffic_stop.hpp"
#include "sdk/cIGZCOMDirector.h"
#include "sdk/cIGZFrameWorkHooks.h"
#include "sdk/cIGZSystemService.h"
#include "sdk/cIGZFrameWork.h"
#include "sdk/cIGZCOM.h"
#include "sdk/cIGZApp.h"
#include "sdk/cIGZMessageTarget2.h"
#include "sdk/cIGZMessage2Standard.h"
#include "sdk/cIGZMessageServer2.h"
#include "sdk/cIGZAllocatorService.h"
#include "sdk/cIGZString.h"
#include "sdk/cISC4App.h"
#include "sdk/cISC4City.h"
#include "sdk/cISTETerrainMap.h"
#include "sdk/cISC4OccupantManager.h"
#include "sdk/cISC4OccupantFilter.h"
#include "sdk/cISC4NetworkOccupant.h"
#include "sdk/cISC4Simulator.h"
#include "sdk/cISC4OrdinanceSimulator.h"
#include "sdk/cISC4Automaton.h"
#include "sdk/cISC4AutomataManager.h"
#include "sdk/cISC4AutomataControllerManager.h"
#include "sdk/cISC4CrimeSimulator.h"
#include "sdk/cGZPersistResourceKey.h"
#include "include/owned_vehicle_creation.hpp"

static void* module;
static char log_path[512],ini_path[512];
static unsigned length(const char* s){unsigned n=0;while(s[n])++n;return n;}
static bool equal(const char*a,const char*b){if(!a||!b)return false;while(*a && *a==*b){++a;++b;}return *a==*b;}
#ifndef SC4_SPEEDING_DEBUG
#define SC4_SPEEDING_DEBUG 0
#endif
#if SC4_SPEEDING_DEBUG
static void log_line(const char* s){
    HANDLE f=CreateFileA(log_path,4,3,nullptr,4,128,nullptr);
    if(f!=reinterpret_cast<HANDLE>(-1)){DWORD n;WriteFile(f,s,length(s),&n,nullptr);WriteFile(f,"\r\n",2,&n,nullptr);CloseHandle(f);}
}
#else
static void log_line(const char*){}
#endif
static void paths(){
    GetModuleFileNameA(module,log_path,480);unsigned n=length(log_path);
    while(n && log_path[n-1]!='\\' && log_path[n-1]!='/')--n;
    const char* l="SC4Speeding.log";for(unsigned i=0;i<=length(l);++i)log_path[n+i]=l[i];
    for(unsigned i=0;i<n;++i)ini_path[i]=log_path[i];
    const char* in="SC4Speeding.ini";for(unsigned i=0;i<=length(in);++i)ini_path[n+i]=in[i];
}
static bool supported(){
    auto b=reinterpret_cast<const unsigned char*>(GetModuleHandleA(nullptr));
    if(reinterpret_cast<uintptr_t>(b)!=0x400000)return false;
    auto pe=*reinterpret_cast<const uint32_t*>(b+0x3c);
    if(*reinterpret_cast<const uint32_t*>(b+pe)!=0x4550)return false;
    if(*reinterpret_cast<const uint16_t*>(b+pe+4)!=0x14c)return false;
    if(*reinterpret_cast<const uint32_t*>(b+pe+24+56)!=0x7c8000)return false;
    const unsigned char create[]={0x8b,0x54,0x24,0x10,0x56,0x57,0x8b,0xf9};
    
    for(unsigned i=0;i<sizeof(create);++i)if(b[0x105370+i]!=create[i])return false;
    // Verify the actual SDK interface layout for this executable.
    auto vt=reinterpret_cast<const uintptr_t*>(b+0x69bd88);
    return vt[15]==0x505370 && vt[16]==0x553080 && vt[25]==0x50be90 &&
           *reinterpret_cast<const uintptr_t*>(b+0x6b0dc8+11*4)==0x6a1960 &&
           *reinterpret_cast<const uintptr_t*>(b+0x6b7ee0+67*4)==0x99bdbb &&
           *reinterpret_cast<const uintptr_t*>(b+0x6b7ee0+68*4)==0x99db6b;
}
// cIGZWin SDK: recursive child lookup 35; GetArea() 48; SetArea(rect) 54.
// Native EXE: GetFlag slot67 (99bdbb), SetFlag slot68 (99db6b).
// Window references are borrowed for this call only, never retained across ticks.
struct WinRect {int32_t l,t,r,b;};
static void* ui_child(void* w,uint32_t id){
    if(!w)return nullptr;auto v=*reinterpret_cast<uintptr_t**>(w);
    return reinterpret_cast<void*(__thiscall*)(void*,uint32_t)>(v[35])(w,id);
}
static WinRect ui_rect(void* w){
    auto v=*reinterpret_cast<uintptr_t**>(w);
    return *reinterpret_cast<const WinRect*(__thiscall*)(void*)>(v[48])(w);
}
static bool ui_area(void* w,const WinRect& r){
    auto v=*reinterpret_cast<uintptr_t**>(w);
    reinterpret_cast<bool(__thiscall*)(void*,const WinRect&)>(v[54])(w,r);
    // Some window subclasses report no change after applying/reflowing an
    // area. Judge the requested geometry by readback, not that return flag.
    auto actual=ui_rect(w);
    return actual.l==r.l&&actual.t==r.t&&actual.r==r.r&&actual.b==r.b;
}
// cIGZWin::GetWindowManager slot6; cIGZWinMgr::IsModal slot42.
// Read the UI's modal state rather than treating every hidden sim pause as a menu.
static bool modal_ui_open(cISC4App* app){
    auto main=app->GetMainWindow();if(!main)return false;
    auto v=*reinterpret_cast<uintptr_t**>(main);
    auto manager=reinterpret_cast<void*(__thiscall*)(void*)>(v[6])(main);
    if(!manager)return false;
    auto m=*reinterpret_cast<uintptr_t**>(manager);
    return reinterpret_cast<bool(__thiscall*)(void*)>(m[42])(manager);
}
static void log_panel_rect(const char* label,const WinRect& r){
    char line[160];unsigned n=0;const char* prefix="Crime UI rect ";
    while(*prefix)line[n++]=*prefix++;
    while(*label&&n<100)line[n++]=*label++;
    const int32_t values[]={r.l,r.t,r.r,r.b};
    for(auto value:values){line[n++]=' ';uint32_t v;
        if(value<0){line[n++]='-';v=uint32_t(-int64_t(value));}else v=uint32_t(value);
        char digits[10];unsigned k=0;do{digits[k++]=char('0'+v%10);v/=10;}while(v);
        while(k)line[n++]=digits[--k];
    }
    line[n]=0;log_line(line);
}
static bool same_rect(const WinRect& a,const WinRect& b){return a.l==b.l&&a.t==b.t&&a.r==b.r&&a.b==b.b;}
static bool crime_selected(void* panel){
    auto legend=ui_child(panel,0x8a2871c4),button=ui_child(panel,0x5003);
    if(!legend||!button)return false;
    auto v=*reinterpret_cast<uintptr_t**>(legend);
    if(!reinterpret_cast<bool(__thiscall*)(void*,uint32_t)>(v[67])(legend,1))return false;
    void* btn=nullptr;auto b=*reinterpret_cast<uintptr_t**>(button);
    if(!reinterpret_cast<bool(__thiscall*)(void*,uint32_t,void**)>(b[0])(button,0x8810,&btn)||!btn)return false;
    auto bv=*reinterpret_cast<uintptr_t**>(btn);
    bool selected=reinterpret_cast<bool(__thiscall*)(void*)>(bv[10])(btn);
    reinterpret_cast<uint32_t(__thiscall*)(void*)>(bv[2])(btn);
    return selected;
}
static void crime_backings(void* panel,bool show){
    struct BackgroundState {void* parent{};bool changed=false,was_visible=false;};
    static BackgroundState states[3];
    const uint32_t ids[]={0xaa32bcd4u,0xaa32bcd5u,0xf5ee0183u};
    for(unsigned i=0;i<3;++i){
        auto parent=ui_child(panel,ids[i]);auto cover=ui_child(parent,0xf5ee0180);
        auto stock=ui_child(parent,0x6a2871bc);if(!cover||!stock)continue;
        auto v=*reinterpret_cast<uintptr_t**>(cover),sv=*reinterpret_cast<uintptr_t**>(stock);
        bool visible=reinterpret_cast<bool(__thiscall*)(void*,uint32_t)>(v[67])(cover,1);
        bool stock_visible=reinterpret_cast<bool(__thiscall*)(void*,uint32_t)>(sv[67])(stock,1);
        auto& state=states[i];
        if(state.parent!=parent){state.parent=parent;state.changed=false;}
        if(show){
            if(!state.changed){state.was_visible=stock_visible;state.changed=true;}
            if(!visible)reinterpret_cast<uint32_t(__thiscall*)(void*,uint32_t,bool)>(v[68])(cover,1,true);
            // The replacement has transparent edges; leaving the original
            // visible produces a second ledge/frame through those pixels.
            if(stock_visible)reinterpret_cast<uint32_t(__thiscall*)(void*,uint32_t,bool)>(sv[68])(stock,1,false);
        }else{
            if(visible)reinterpret_cast<uint32_t(__thiscall*)(void*,uint32_t,bool)>(v[68])(cover,1,false);
            if(state.changed){
                if(!stock_visible && state.was_visible)reinterpret_cast<uint32_t(__thiscall*)(void*,uint32_t,bool)>(sv[68])(stock,1,true);
                state.changed=false;
            }
        }
    }
}
struct CrimePanelLayout {
    void* identity{};bool active=false,blocked=false;
    struct Saved {uint32_t id;bool backing;WinRect before,after;bool present;} saved[10]{};
    void* resolve(void* panel,const Saved& s){auto w=s.id?ui_child(panel,s.id):panel;return s.backing?ui_child(w,0x6a2871bc):w;}
    void conflict(){if(!blocked)log_line("Crime UI: panel layout conflict detected; automatic resizing skipped.");blocked=true;}
    void update(void* panel,bool selected){
        if(identity!=panel){identity=panel;active=false;blocked=false;}
        if(!selected)crime_backings(panel,false);
        if(blocked){
            // A conflict must not strand our own root at the raised height.
            if(!selected && active && same_rect(ui_rect(panel),saved[0].after))ui_area(panel,saved[0].before);
            if(!selected)active=false;
            return;
        }
        if(active){
            if(selected){
                for(auto& s:saved)if(s.present){auto w=resolve(panel,s);if(!w||!same_rect(ui_rect(w),s.after)){conflict();return;}}
                crime_backings(panel,true);return;
            }
            // Restore only rectangles still owned by this change. A native
            // view switch may already have restored individual children.
            bool changed_elsewhere=false;
            for(auto& s:saved)if(s.present){
                auto w=resolve(panel,s);if(!w){changed_elsewhere=true;continue;}
                auto r=ui_rect(w);
                if(same_rect(r,s.after)){if(!same_rect(r,s.before)&&!ui_area(w,s.before))changed_elsewhere=true;}
                else if(!same_rect(r,s.before))changed_elsewhere=true;
            }
            active=false;
            if(changed_elsewhere){conflict();return;}
            log_line("Crime UI: original panel layout restored after leaving Crime.");return;
        }
        if(!selected)return;
        const uint32_t ids[]={0,0xaa32bcd4u,0xaa32bcd5u,0x8a2871c3u,0xaa32bcd4u,0xaa32bcd5u,0x8a2871c3u,0x8a2871b1u,0x8a2871b2u,0xf5ee0183u};
        auto root=ui_rect(panel);int width=root.r-root.l;log_panel_rect("root before",root);
        if((width!=546&&width!=516)||root.b-root.t!=428){conflict();return;}
        // Preflight every target before changing any window. Only the stock
        // shapes and this mod's supplied 20px expanded artwork are accepted.
        for(unsigned i=0;i<10;++i){
            auto& s=saved[i];s.id=ids[i];s.backing=i>=4&&i<=6;
            auto w=resolve(panel,s);s.present=w!=nullptr;
            if(s.backing&&s.id==0x8a2871c3u){s.present=false;continue;}
            if(!w)continue;
            s.before=ui_rect(w);s.after=s.before;log_panel_rect(s.backing?"backing before":"container before",s.before);
            if(i==0){s.after.t-=20;continue;}
            auto r=s.before;int h=r.b-r.t;
            if(i==9){
                if(h!=288||r.r-r.l!=396||r.t!=33||(r.l!=108&&r.l!=142)){conflict();return;}
                s.after.b+=20;
            }else if(i>=7){
                if(h!=130||(r.t!=298&&r.t!=346)||(r.r-r.l!=546&&r.r-r.l!=516)){conflict();return;}
                s.after.t=318;s.after.b=448;
            }else{
                // Original compact layout: aa32bcd5 has a 516px backing
                // at x=1 inside the same 546px container as the full layout.
                bool stock_compact=s.backing&&s.id==0xaa32bcd5u&&r.l==1&&r.r==517;
                if((r.t!=0&&r.t!=-1)||(h!=428&&h!=448)||(r.r-r.l!=546&&r.r-r.l!=516&&!stock_compact)){conflict();return;}
                s.after.b=s.after.t+448;
            }
        }
        if(!saved[7].present||!saved[8].present){conflict();return;}
        for(auto& s:saved)if(s.present){auto w=resolve(panel,s);if(!same_rect(ui_rect(w),s.after)&&!ui_area(w,s.after)){
            log_panel_rect("resize rejected",ui_rect(w));
            // Roll back owned changes if a subclass clamps/rejects a resize.
            for(auto& rollback:saved)if(rollback.present){auto target=resolve(panel,rollback);if(target&&same_rect(ui_rect(target),rollback.after))ui_area(target,rollback.before);}
            conflict();return;
        }}
        active=true;crime_backings(panel,true);log_line("Crime UI: Crime selected; compatible panel enlarged upward by 20 pixels.");
    }
};
static CrimePanelLayout crime_panel_layout;
static void maintain_crime_panel(cISC4App* app){
    auto tag=ui_child(app->GetMainWindow(),0xf5ee0170);if(!tag)return;
    void* panel=tag;bool found=false;
    for(unsigned depth=0;depth<8&&panel;++depth){
        auto vt=*reinterpret_cast<uintptr_t**>(panel);
        if(reinterpret_cast<void*(__thiscall*)(void*,uint32_t)>(vt[34])(panel,0x8a2871b2)){found=true;break;}
        panel=reinterpret_cast<void*(__thiscall*)(void*)>(vt[11])(panel);
    }
    if(found)crime_panel_layout.update(panel,crime_selected(panel));
}
static float sq(float n){return n*n;}
static float root(float n){
    float r;
    __asm {
        fld n
        fsqrt
        fstp r
    }
    return r;
}
static float distance(cS3DVector3 a,cS3DVector3 b){return root(sq(a.fX-b.fX)+sq(a.fZ-b.fZ));}
static cS3DVector3 normalized(cS3DVector3 d){float n=root(sq(d.fX)+sq(d.fZ));return n>.001f?cS3DVector3(d.fX/n,0,d.fZ/n):cS3DVector3(0,0,1);}
static float dot3(cS3DVector3 a,cS3DVector3 b){return a.fX*b.fX+a.fY*b.fY+a.fZ*b.fZ;}
static cS3DVector3 cross3(cS3DVector3 a,cS3DVector3 b){return cS3DVector3(a.fY*b.fZ-a.fZ*b.fY,a.fZ*b.fX-a.fX*b.fZ,a.fX*b.fY-a.fY*b.fX);}
static cS3DVector3 unit3(cS3DVector3 a){float n=root(dot3(a,a));return n>.0001f?cS3DVector3(a.fX/n,a.fY/n,a.fZ/n):cS3DVector3(0,1,0);}
struct NativeTransform {uint8_t flags[4];float rotation[9];cS3DVector3 translation;float scale;};
static_assert(sizeof(NativeTransform)==56);
static constexpr uint32_t SpeedingID=112;
static constexpr uint32_t SpeedTrapsID=0xf5ee0200;
static constexpr cGZPersistResourceKey CrimeIcon{0x7ab50e44, 0x1abe787d, 0xf5ee0070}; // Dedicated SHPI/FSH gauge texture
struct CrimeEvent { uint32_t x,z,id; uint8_t visual; uint8_t pad[3]; cGZPersistResourceKey icon; };
struct EventVector { CrimeEvent* first;CrimeEvent* last;CrimeEvent* capacity; };
static_assert(sizeof(CrimeEvent)==28 && sizeof(EventVector)==12);
using IncidentFunction=bool(__thiscall*)(cISC4CrimeSimulator*,EventVector&);
class NativeEngine;
static NativeEngine* active_engine;
static bool __fastcall incident_hook(cISC4CrimeSimulator*,void*,EventVector&);

// Suppress the native combined emergency switch on our own patrol. Its
// flashing visual is started separately, without the broad traffic attractor.
static void __fastcall scene_emergency_effect(cISC4Automaton*,void*,bool){}
// Synchronous query filter: only bidirectional surface road/street pieces.
class SceneRoadFilter final:public cISC4OccupantFilter {
public:
    bool QueryInterface(uint32_t id,void** out)override{if(!out)return false;*out=nullptr;if(id==1||id==GZIID_cISC4OccupantFilter){*out=this;return true;}return false;}
    uint32_t AddRef()override{return 1;}
    uint32_t Release()override{return 1;}
    bool IsOccupantIncluded(cISC4Occupant* o)override{
        cISC4NetworkOccupant* n=nullptr;
        if(!o||!reinterpret_cast<cIGZUnknown*>(o)->QueryInterface(GZIID_cISC4NetworkOccupant,reinterpret_cast<void**>(&n))||!n)return false;
        bool ok=n->IsOfType(cISC4NetworkOccupant::Road)||n->IsOfType(cISC4NetworkOccupant::Street);
        n->Release();return ok;
    }
    bool IsOccupantTypeIncluded(uint32_t)override{return true;}
    bool IsPropertyHolderIncluded(cISCPropertyHolder*)override{return true;}
};
class NativeEngine final:public speeding::Engine {
    struct Owned { cISC4Automaton* ptr{};cISC4AutomataManager* manager{}; } actors[3];
    uintptr_t* police_original_table{};
    uintptr_t police_table_storage[202]{}; // RTTI locator + 201 native slots.
    bool isolate_police_traffic(cISC4Automaton* police){
        auto table=*reinterpret_cast<uintptr_t**>(police);
        if(table!=reinterpret_cast<uintptr_t*>(0xa9a0c0) || table[194]!=0x530af0){
            log_line("Scene cancelled: police interface differs; traffic isolation unavailable.");return false;
        }
        for(unsigned i=0;i<202;++i)police_table_storage[i]=table[int(i)-1];
        police_original_table=table;
        police_table_storage[195]=reinterpret_cast<uintptr_t>(&scene_emergency_effect);
        *reinterpret_cast<uintptr_t**>(police)=police_table_storage+1;
        reinterpret_cast<void(__thiscall*)(cISC4Automaton*,bool)>(0x530af0)(police,false);
        log_line("Scene police isolated: nearby-traffic pull-over effect suppressed.");return true;
    }
    uintptr_t* old_table{};
    uintptr_t map_table[64]{};
    IncidentFunction original{};
    bool owns_map_hook=false;
    uint32_t marker_x=0,marker_z=0;
    bool marker=false, walking=false, lhd=false, valid=false;
    bool officer_turning=false;
    bool ordinance_ready=false,ordinance_warning=false;DWORD ordinance_wait_started=0;
    float officer_turn_elapsed=0;
    cS3DVector3 officer_facing{0,0,1},officer_turn_start{},officer_turn_target{};
    cS3DVector3 heading{0,0,1},previous{},target{},officer_position{};
    bool have_previous=false, stopping=false, paired_stop=false;
    float drive_elapsed=0,curve_elapsed=0,curve_distance=9,curve_gap=8,following_gap=10;
    static constexpr float police_delay=.65f;
    float ground_offset[2]{.05f,.05f};
    static constexpr float drive_speed=6;
    cS3DVector3 drive_offender{},drive_police{},scene_target{};
    bool lights_on=false;
    bool local_request=false;cS3DVector3 request_center{};
    cS3DVector3 curve_offender{},curve_police{},curve_correction{};
    float shoulder_offset=2.0f;
    float rear_clearance()const {return following_gap+actors[1].ptr->GetRadius();}
    float front_clearance()const {return drive_speed*2+9+actors[0].ptr->GetRadius();}
    cISTETerrainMap* terrain()const {return reinterpret_cast<cISTETerrainMap*>(city->GetTerrain());}
    bool surface_height(const cS3DVector3& p,float& y){
        auto t=terrain();if(!t || !t->LocationIsInBounds(p.fX,p.fZ))return false;
        auto manager=city->GetOccupantManager();cISC4Occupant* occupant=nullptr;
        SceneRoadFilter filter;
        if(manager && manager->GetFirstOccupantByPosition(occupant,p.fX,p.fZ,&filter) && occupant){
            cISC4NetworkOccupant* network=nullptr;
            if(reinterpret_cast<cIGZUnknown*>(occupant)->QueryInterface(GZIID_cISC4NetworkOccupant,reinterpret_cast<void**>(&network)) && network){
                bool road=network->IsOfType(cISC4NetworkOccupant::Road)||network->IsOfType(cISC4NetworkOccupant::Street);
                if(road){
                    // Native slot56,6197f0 accepts world X/Z and returns x87 float.
                    y=network->GetAltitude(p.fX,p.fZ);network->Release();
                    return __builtin_isfinite(y);
                }
                network->Release();
            }
        }
        y=t->GetAltitude(p.fX,p.fZ);return __builtin_isfinite(y);
    }
    bool ground_height(cS3DVector3& p,float offset){
        float y;if(!surface_height(p,y))return false;p.fY=y+offset;return true;
    }
    bool ground_pose(unsigned id,cS3DVector3 p,cS3DVector3 direction){
        auto a=actor(id);if(!a)return false;
        direction=normalized(direction);
        cS3DVector3 right(direction.fZ,0,-direction.fX);
        float h[4];
        // Approximate wheel contacts, spanning road-piece boundaries. This
        // follows the actual network surface and blends pitch as axles cross.
        for(unsigned i=0;i<4;++i){
            float fore=i<2?1.5f:-1.5f,side=(i&1)?.7f:-.7f;
            cS3DVector3 q(p.fX+direction.fX*fore+right.fX*side,p.fY,p.fZ+direction.fZ*fore+right.fZ*side);
            if(!surface_height(q,h[i]))return false;
        }
        float center;if(!surface_height(p,center))return false;
        float support=(h[0]+h[1]+h[2]+h[3])*.25f;
        if(support<center)support=center; // Keep the body above a convex crest.
        p.fY=support+ground_offset[id-1];
        cS3DVector3 longitudinal(direction.fX,(h[0]+h[1]-h[2]-h[3])/6.0f,direction.fZ);
        cS3DVector3 transverse(right.fX,(h[1]+h[3]-h[0]-h[2])/2.8f,right.fZ);
        auto n=unit3(cross3(longitudinal,transverse));if(n.fY<.15f)return false;
        float d=dot3(direction,n);
        auto f=unit3(cS3DVector3(direction.fX-n.fX*d,direction.fY-n.fY*d,direction.fZ-n.fZ*d));
        auto r=unit3(cross3(n,f));f=unit3(cross3(r,n));
        auto table=*reinterpret_cast<uintptr_t**>(a);
        if(table[75]!=0x509440){log_line("Scene cancelled: native transform setter differs.");return false;}
        a->SetPosition(p);a->SetOrientation(f);
        NativeTransform tr{};
        if(!reinterpret_cast<bool(__thiscall*)(cISC4Automaton*,NativeTransform*)>(table[12])(a,&tr))return false;
        tr.flags[0]=2;tr.flags[1]=5;
        tr.rotation[0]=r.fX;tr.rotation[1]=n.fX;tr.rotation[2]=f.fX;
        tr.rotation[3]=r.fY;tr.rotation[4]=n.fY;tr.rotation[5]=f.fY;
        tr.rotation[6]=r.fZ;tr.rotation[7]=n.fZ;tr.rotation[8]=f.fZ;
        tr.translation=p;
        return reinterpret_cast<bool(__thiscall*)(cISC4Automaton*,const NativeTransform*)>(table[75])(a,&tr);
    }
    bool road_without_junction(const cS3DVector3& p,uint32_t* axis=nullptr){
        auto manager=city->GetOccupantManager();if(!manager)return false;
        SceneRoadFilter filter;cISC4Occupant* occupant=nullptr;
        if(!manager->GetFirstOccupantByPosition(occupant,p.fX,p.fZ,&filter)||!occupant)return false;
        cISC4NetworkOccupant* network=nullptr;
        if(!reinterpret_cast<cIGZUnknown*>(occupant)->QueryInterface(GZIID_cISC4NetworkOccupant,reinterpret_cast<void**>(&network))||!network)return false;
        bool road=network->IsOfType(cISC4NetworkOccupant::Road);
        bool street=network->IsOfType(cISC4NetworkOccupant::Street);
        uint32_t edges=road?network->GetActiveEdgesForType(cISC4NetworkOccupant::Road):
            (street?network->GetActiveEdgesForType(cISC4NetworkOccupant::Street):0);
        // Native network edges are four cyclic bits. Exactly two opposite
        // edges (0101 or1010) exclude corners, T/cross junctions and dead ends.
        bool ok=!network->IsIntersection()&&(road||street)&&(edges==5||edges==10)&&network->GetActiveEdges()==edges;
        if(axis)*axis=edges;
        network->Release();return ok;
    }
    bool eligible_start_lot(const cS3DVector3& lead){
        auto manager=city->GetLotManager();if(!manager)return false;
        // Probe inside the first tile, just past the aligned rear boundary.
        int x=0,z=0;
        city->PositionToCell(lead.fX-heading.fX*(rear_clearance()-.25f),
                             lead.fZ-heading.fZ*(rear_clearance()-.25f),x,z);
        const int dx[4]={-1,1,0,0},dz[4]={0,0,-1,1};
        auto table=*reinterpret_cast<uintptr_t**>(manager);
        // cISC4LotManager::GetLot(vector), native MSVC overload order: slot5.
        using GetLot=void*(__thiscall*)(cISC4LotManager*,const cS3DVector3&);
        for(unsigned i=0;i<4;++i){
            cS3DVector3 p((float(x+dx[i])+.5f)*16,lead.fY,(float(z+dz[i])+.5f)*16);
            if(p.fX<0||p.fZ<0||p.fX>=city->SizeX()||p.fZ>=city->SizeZ())continue;
            void* lot=reinterpret_cast<GetLot>(table[5])(manager,p);if(!lot)continue;
            auto lot_table=*reinterpret_cast<uintptr_t**>(lot);
            // GetBuildingType is an exemplar ID, not a developer category.
            // Read purpose/wealth from the building's native profile instead.
            void* building=reinterpret_cast<void*(__thiscall*)(void*)>(lot_table[48])(lot);
            if(!building)continue;
            auto building_table=*reinterpret_cast<uintptr_t**>(building);
            auto profile=reinterpret_cast<const uint32_t*(__thiscall*)(void*)>(building_table[11])(building);
            if(profile && (profile[0]==1 || profile[0]==2) && profile[1]==1)return true;

        }
        return false;
    }
    bool straight_corridor(const cS3DVector3& origin,const cS3DVector3& direction,float back,float ahead){
        uint32_t axis=0;
        auto check=[&](float d){
            cS3DVector3 point(origin.fX+direction.fX*d,origin.fY,origin.fZ+direction.fZ*d);
            uint32_t current=0;
            if(!road_without_junction(point,&current))return false;
            if(axis&&current!=axis)return false;
            axis=current;return true;
        };
        // Test build: no extra clearance beyond the requested maneuver span.
        // The maneuver itself must still lie on a straight road/street.
        float first=back,last=ahead;
        for(float d=first;d<last;d+=2)if(!check(d))return false;
        return check(last); // Always test the exact far endpoint.
    }
    bool set_lights(bool enabled){
        auto police=actor(2);
        if(!police){lights_on=false;return !enabled;}
        if(enabled && !lights_on){
            // Native emergency visual (effect 2), without the combined
            // emergency switch that also creates automata_pullover.
            auto table=*reinterpret_cast<uintptr_t**>(police);
            auto output=reinterpret_cast<void**>(reinterpret_cast<char*>(police)+0x2d0);
            using Visual=bool(__thiscall*)(cISC4Automaton*,uint32_t,void**);
            bool ok=reinterpret_cast<Visual>(table[99])(police,2,output);
            lights_on=ok && *output;
            log_line(lights_on?"Police flashing lights enabled; audio disabled.":"Scene cancelled: police flashing-light effect unavailable.");
            return lights_on;
        }
        if(!enabled && lights_on){reinterpret_cast<void(__thiscall*)(cISC4Automaton*,bool)>(0x530af0)(police,false);lights_on=false;}
        return true;
    }
public:
    NativeEngine* next_scene=nullptr;
    cISC4City* city{};
    cIGZAllocatorService* allocator{};
    cISC4CrimeSimulator* crimes{};
    DWORD thread{};
    cISC4Automaton* actor(speeding::Actor h) const {return h>=1&&h<=3?actors[h-1].ptr:nullptr;}
    cS3DVector3 position(cISC4Automaton* a) const {cS3DVector3 p;a->GetPosition(p);return p;}
    cS3DVector3 roadside()const {return lhd?cS3DVector3(heading.fZ,0,-heading.fX):cS3DVector3(-heading.fZ,0,heading.fX);}
    cS3DVector3 side()const {auto r=roadside();return cS3DVector3(-r.fX,0,-r.fZ);}
    void set_selection_enabled(bool enabled){
        auto begin=*reinterpret_cast<uintptr_t**>(0xb48620),end=*reinterpret_cast<uintptr_t**>(0xb48624);
        if(!begin||end<begin||end-begin>512)return;
        for(auto i=begin;i!=end;++i)if(*i && *reinterpret_cast<uint32_t*>(*i)==SpeedingID){
            auto weight=reinterpret_cast<float*>(*i+0x38);
            // Only our unique crime category is changed; restore baseline4.
            if(*weight==0 || *weight==4){
                float next=enabled?4.0f:0.0f;
                if(*weight!=next)log_line(enabled?"Native Speeding selection enabled: weight4.":"Native Speeding selection disabled by ordinance eligibility.");
                *weight=next;
            }
            return;
        }
    }
    void request_near(const cS3DVector3* center){local_request=center!=nullptr;if(center)request_center=*center;}
    bool category_loaded(){
        // Verified dynamic category registry for this exact executable.
        auto begin=*reinterpret_cast<uintptr_t**>(0xb48620),end=*reinterpret_cast<uintptr_t**>(0xb48624);
        if(!begin||end<begin||end-begin>512)return false;
        for(auto i=begin;i!=end;++i){
            if(*i && *reinterpret_cast<uint32_t*>(*i)==SpeedingID){
                auto name=reinterpret_cast<cIGZString*>(*i+4)->ToChar();
                if(!equal(name,"Speeding") || *reinterpret_cast<float*>(*i+0x38)!=4.0f)return false;
                auto masks=reinterpret_cast<const uint32_t*>(*i+0x18);
                if(!masks[0]||!masks[1]||!masks[2]||!masks[3]){
                    log_line("Disabled: Speeding native lot filter is empty. Replace SC4Speeding.dat with version0.48 or newer.");return false;
                }
                log_line("Native Speeding category loaded: weight4 and nonzero lot filters.");return true;
            }
        }return false;
    }
    void bind_scene(NativeEngine& owner){
        city=owner.city;allocator=owner.allocator;crimes=owner.crimes;thread=owner.thread;
        lhd=owner.lhd;shoulder_offset=owner.shoulder_offset;valid=city!=nullptr;
        owns_map_hook=false;marker=false;
    }
    bool bind(cISC4City* c,cIGZAllocatorService* alloc){
        city=c;allocator=alloc;thread=GetCurrentThreadId();
        if(!city || !allocator || !category_loaded()){log_line("Disabled: missing/conflicting Speeding crime record (DAT required).");city=nullptr;return false;}
        crimes=city->GetCrimeSimulator();auto vehicles=city->GetVehicleManager();
        if(!crimes || !vehicles || !city->GetPedestrianManager()){log_line("Disabled: required city services unavailable.");city=nullptr;return false;}
        old_table=*reinterpret_cast<uintptr_t**>(crimes);
        auto vm=*reinterpret_cast<uintptr_t**>(vehicles);
        if(old_table[11]!=0x6a1960 || vm[15]!=0x505370 || vm[16]!=0x553080 || vm[69]!=0x54fbc0){
            log_line("Disabled: native interface differs or another mod already hooks it.");city=nullptr;return false;
        }
        for(unsigned i=0;i<64;++i)map_table[i]=old_table[i];
        owns_map_hook=true;original=reinterpret_cast<IncidentFunction>(old_table[11]);
        map_table[11]=reinterpret_cast<uintptr_t>(&incident_hook);
        *reinterpret_cast<uintptr_t**>(crimes)=map_table;
        __atomic_store_n(&active_engine,this,__ATOMIC_RELEASE);valid=true;lhd=GetPrivateProfileIntA("Speeding","LeftHandDrive",0,ini_path)!=0;
        unsigned offset_cm=GetPrivateProfileIntA("Speeding","ShoulderOffsetCentimeters",200,ini_path);
        if(offset_cm<25)offset_cm=25;if(offset_cm>300)offset_cm=300;
        shoulder_offset=float(offset_cm)*.01f;
        ordinance_ready=false;ordinance_warning=false;ordinance_wait_started=GetTickCount();
        log_line("Speed Traps: waiting for host registration.");
        set_selection_enabled(speed_traps_available()&&!speed_traps_on());
        log_line("City attached; isolated incident-array hook installed.");return true;
    }
    void unbind(){
        set_lights(false);marker=false;walking=false;local_request=false;
        if(valid && owns_map_hook)set_selection_enabled(true);
        if(valid && owns_map_hook && crimes && *reinterpret_cast<uintptr_t**>(crimes)==map_table)*reinterpret_cast<uintptr_t**>(crimes)=old_table;
        valid=false;city=nullptr;crimes=nullptr;if(owns_map_hook){__atomic_store_n(&active_engine,static_cast<NativeEngine*>(nullptr),__ATOMIC_RELEASE);log_line("City detached.");}owns_map_hook=false;
    }
    // No dereference of possibly destroyed city services on a missed shutdown.
    void context_lost(){if(owns_map_hook)set_selection_enabled(true);lights_on=false;marker=false;walking=false;valid=false;city=nullptr;crimes=nullptr;if(owns_map_hook)__atomic_store_n(&active_engine,static_cast<NativeEngine*>(nullptr),__ATOMIC_RELEASE);owns_map_hook=false;for(auto& a:actors)a={};police_original_table=nullptr;log_line("City changed without shutdown notification; stale handles abandoned.");}
    bool hooked_incidents(cISC4CrimeSimulator* self,EventVector& v){
        bool result=original(self,v);
        if(thread!=GetCurrentThreadId())return result;
        uintptr_t start=reinterpret_cast<uintptr_t>(v.first),end=reinterpret_cast<uintptr_t>(v.last),cap=reinterpret_cast<uintptr_t>(v.capacity);
        if(end<start || cap<end || (end-start)%sizeof(CrimeEvent) || end-start>10000000)return result;
        // Native monthly Speeding records supply the selection/count, while
        // this DLL retains its marker until the next completed crime selection.
        auto output=v.first;
        for(auto it=v.first;it!=v.last;++it)if(it->id!=SpeedingID)*output++=*it;
        v.last=output;
        if(!valid || self!=crimes || speed_traps_on() || !speed_traps_available())return v.last!=v.first;
        for(auto scene=this;scene;scene=scene->next_scene){
            if(!scene->valid || !scene->marker)continue;
            if(v.last==v.capacity){
                unsigned n=unsigned(v.last-v.first);
                auto buffer=static_cast<CrimeEvent*>(allocator->Allocate((n+1)*sizeof(CrimeEvent)));
                if(!buffer)return v.last!=v.first;
                for(unsigned i=0;i<n;++i)buffer[i]=v.first[i];
                if(v.first)allocator->Deallocate(v.first);
                v.first=buffer;v.last=buffer+n;v.capacity=buffer+n+1;
            }
            *v.last++=CrimeEvent{scene->marker_x,scene->marker_z,SpeedingID,1,{0,0,0},CrimeIcon};
        }
        return v.last!=v.first;
    }

    void make_speed_traps_available(){
        if(ordinance_ready || !city)return;
        auto ordinances=city->GetOrdinanceSimulator();
        if(ordinances && ordinances->GetOrdinanceByID(SpeedTrapsID)){
            // Host conditions now include police count and R$/CS$ population.
            // Native monthly updates must control availability; never force it.
            log_line("Speed Traps: registered; ordinance host controls eligibility requirements.");
            ordinance_ready=true;return;
        }
        if(!ordinance_warning && DWORD(GetTickCount()-ordinance_wait_started)>=5000){
            ordinance_warning=true;
            log_line("Speed Traps NOT REGISTERED: check SC4CustomOrdinanceHost.log and its ordinance folder path; SC4Speeding-SpeedTraps.dat must be in that folder.");
        }
    }
    bool speed_traps_available()const{
        auto ordinances=city?city->GetOrdinanceSimulator():nullptr;
        return ordinances && ordinances->GetOrdinanceByID(SpeedTrapsID) && ordinances->IsOrdinanceAvailable(SpeedTrapsID);
    }
    bool speed_traps_on()const{
        auto ordinances=city?city->GetOrdinanceSimulator():nullptr;
        return ordinances && ordinances->IsOrdinanceOn(SpeedTrapsID);
    }
    bool owned_and_alive(speeding::Actor a) const override {auto ptr=actor(a);return valid && ptr && !ptr->CheckAutomataFlag(cISC4Automaton::AutomataFlagRemove);}
    bool create(unsigned slot,cISC4AutomataManager* manager,uint32_t group,const cS3DVector3& pos,const cS3DVector3* direction){
        if(!manager || slot>=3)return false;
        cISC4AutomataManager::tExemplarData* exemplar=nullptr;
        for(unsigned attempt=0;attempt<40;++attempt){
            exemplar=manager->ChooseRandomExemplar(group,cISC4AutomataManager::PopulateLayer::None,-1,-1);
            if(!exemplar){return false;}
            if(slot!=0)break;
            auto name=exemplar->exemplarName.AsIGZString()->ToChar();
            bool car=false;
            if(name){for(unsigned i=0;name[i];++i){
                if((name[i]=='S'&&name[i+1]=='e'&&name[i+2]=='d'&&name[i+3]=='a'&&name[i+4]=='n') ||
                   (name[i]=='S'&&name[i+1]=='p'&&name[i+2]=='o'&&name[i+3]=='r'&&name[i+4]=='t'&&name[i+5]=='s')){car=true;break;}
            }}
            if(car)break;exemplar=nullptr;
        }
        if(!exemplar){return false;}
        auto key=reinterpret_cast<const cGZPersistResourceKey*>(reinterpret_cast<const char*>(exemplar)+16);
        cISC4Automaton* a=nullptr;
        if(slot<2 && owned_vehicle_creation_supported(manager))
            a=owned_vehicle_outer(manager,nullptr,group,pos,0,*key,nullptr,0,direction);
        else a=manager->CreateAutomaton(group,pos,0,*key,nullptr,0,direction);
        if(!a)return false;
        a->AddRef();actors[slot]={a,manager};
        a->SetPriority(0);a->SetOpacity(0,0);return true;
    }
    bool prepare(speeding::StopPlan& plan)override{
        if(!valid || !city){log_line("Search blocked: city integration unavailable.");return false;}
        if(!speed_traps_available() || speed_traps_on()){log_line("Search blocked: ordinance unavailable or enacted.");return false;}
        for(auto&a:actors)if(a.ptr){log_line("Search blocked: previous owned actor handle remains.");return false;}

        auto manager=city->GetVehicleManager();
        if(!manager){log_line("Scene skipped: vehicle manager unavailable.");return false;}
        cS3DVector3 center(city->SizeX()*.5f,city->GetWorldBaseElevation(),city->SizeZ()*.5f),p,dir;
        bool use_local=local_request;local_request=false;
        if(use_local)center=request_center;
        float search_radius=use_local?48.0f:city->SizeX()*.65f;
        bool found=false;
        // One anchor and one straight corridor. The patrol is never assigned
        // an independent random road point or a separate lane.
        for(unsigned road=0;road<32 && !found;++road){
            if(!manager->GetRandomCreationPoint(0x4002,center,0,search_radius,p,0,nullptr)){continue;}
            if(!__builtin_isfinite(p.fX)||!__builtin_isfinite(p.fY)||!__builtin_isfinite(p.fZ)){continue;}
            if(use_local && distance(p,center)>search_radius){continue;}
            if(!road_without_junction(p)){continue;}
            if(!create(0,manager,0x4002,p,nullptr)){
                continue;
            }
            actors[0].ptr->SetVisible(false);actors[0].ptr->GetOrientation(dir);
            if(!__builtin_isfinite(dir.fX)||!__builtin_isfinite(dir.fZ)||sq(dir.fX)+sq(dir.fZ)<.01f){remove_owned(1);continue;}
            heading=normalized(dir);p=position(actors[0].ptr);
            cS3DVector3 police_pos(p.fX-heading.fX*10,p.fY,p.fZ-heading.fZ*10);
            if(!create(1,manager,0x4228,police_pos,&heading)){remove_owned(1);continue;}
            following_gap=actors[0].ptr->GetRadius()+actors[1].ptr->GetRadius()+3;
            if(following_gap<8)following_gap=8;following_gap+=2;
            police_pos=cS3DVector3(p.fX-heading.fX*following_gap,p.fY,p.fZ-heading.fZ*following_gap);
            actors[1].ptr->SetVisible(false);actors[1].ptr->SetPosition(police_pos);
            actors[1].ptr->SetOrientation(heading);
            // Begin the complete scene footprint at the next tile boundary
            // in the direction of travel. Preserve the lane's lateral position.
            bool along_x=sq(heading.fX)>sq(heading.fZ);
            float direction=along_x?heading.fX:heading.fZ;
            if(sq(direction)<.99f){remove_owned(2);remove_owned(1);continue;}
            float edge=(along_x?p.fX:p.fZ)-direction*rear_clearance();
            float cell=edge/16.0f;
            int whole=static_cast<int>(cell);if(float(whole)>cell)--whole;
            float boundary=float(whole)*16.0f;
            if(direction>0 && edge-boundary>.001f)boundary+=16.0f;
            float advance=(boundary-edge)/direction;
            // Spawn-height offsets are not a road eligibility condition.
            // Place both cars directly on the sampled drivable surface.
            constexpr float surface_offset=.05f;
            p.fX+=heading.fX*advance;p.fZ+=heading.fZ*advance;
            police_pos.fX+=heading.fX*advance;police_pos.fZ+=heading.fZ*advance;
            if(!ground_height(p,surface_offset)){remove_owned(2);remove_owned(1);continue;}
            if(!ground_height(police_pos,surface_offset)){remove_owned(2);remove_owned(1);continue;}
            actors[0].ptr->SetPosition(p);actors[1].ptr->SetPosition(police_pos);
            // Use the actual rear car footprint instead of a fixed -16m
            // check or extra padding behind an already passed junction.
            float rear=rear_clearance();
            float front=front_clearance();
            if(!straight_corridor(p,heading,-rear,front)){
                remove_owned(2);remove_owned(1);continue;
            }
            if(!eligible_start_lot(p)){remove_owned(2);remove_owned(1);continue;}
            found=true;
        }
        if(!found){log_line("Scene deferred: no suitable road/lot candidate found.");return false;}
        have_previous=false;walking=false;stopping=false;paired_stop=false;drive_elapsed=curve_elapsed=0;lights_on=false;
        actors[0].ptr->SetVisible(true);actors[1].ptr->SetVisible(true);
        if(!isolate_police_traffic(actors[1].ptr)){remove_owned(2);remove_owned(1);return false;}
        float baseline=actors[0].ptr->GetDefaultSpeed();
        if(!__builtin_isfinite(baseline)||baseline<=0){log_line("Search finalization failed: invalid vehicle default speed.");remove_owned(2);remove_owned(1);return false;}
        drive_offender=position(actor(1));drive_police=position(actor(2));
        ground_offset[0]=ground_offset[1]=.05f;
        curve_gap=following_gap-2;
        auto r=roadside();
        scene_target=cS3DVector3(drive_offender.fX+heading.fX*(drive_speed*2+9-curve_gap*.5f)+r.fX*shoulder_offset,drive_offender.fY,drive_offender.fZ+heading.fZ*(drive_speed*2+9-curve_gap*.5f)+r.fZ*shoulder_offset);
        if(!ground_height(scene_target,ground_offset[0])){log_line("Search finalization failed: camera/stop target surface sample unavailable.");remove_owned(2);remove_owned(1);return false;}
        plan={1,2,baseline,baseline*1.5f};return true;
    }
    bool begin_pursuit(speeding::Actor police,speeding::Actor offender,float)override{
        speeding::Actor pair[2]={offender,police};
        for(auto id:pair){auto a=actor(id);a->SetState(7,nullptr,-1,false,0,0,nullptr);a->SetSpeed(0,0);a->SetOpacity(0,0);a->SetOrientation(heading);}
        if(!set_lights(true))return false;
        log_line("Moving fade-in started: both cars advance immediately.");return true;
    }
    // Legacy core callback name: visual lights only; no audio is opened.
    bool set_siren(speeding::Actor,bool enabled)override{return set_lights(enabled);}
    bool focus_scene(){
        if(!valid || !owned_and_alive(1))return false;
        auto renderer=*reinterpret_cast<void**>(0xb43dd0);if(!renderer){log_line("Camera pan unavailable: renderer missing.");return false;}
        auto table=*reinterpret_cast<uintptr_t**>(renderer);
        auto control=reinterpret_cast<void*(__thiscall*)(void*)>(table[16])(renderer);
        if(!control){log_line("Camera pan unavailable: camera control missing.");return false;}
        bool ok=reinterpret_cast<bool(__thiscall*)(void*,const cS3DVector3*)>(0x7cd810)(control,&scene_target);
        log_line(ok?"Camera centered on planned pull-over location.":"Camera pan failed.");return ok;
    }
    bool request_safe_stop(speeding::Actor offender,speeding::Actor police)override{
        auto a=position(actor(offender)),b=position(actor(police));
        curve_distance=drive_speed*1.5f;
        curve_gap=following_gap-2;
        // The entire remaining maneuver must still avoid curves/junctions.
        if(!straight_corridor(a,heading,-following_gap-actor(police)->GetRadius(),curve_distance+actor(offender)->GetRadius())){
            log_line("Scene cancelled: remaining animation reaches a curve or intersection.");return false;
        }
        curve_offender=a;curve_police=b;
        curve_correction=cS3DVector3(a.fX-heading.fX*curve_gap-b.fX,a.fY-b.fY,a.fZ-heading.fZ*curve_gap-b.fZ);
        for(unsigned i=1;i<=2;++i){actor(i)->SetState(7,nullptr,-1,false,0,0,nullptr);actor(i)->SetSpeed(0,0);actor(i)->SetOpacity(1,0);}
        stopping=true;paired_stop=false;curve_elapsed=0;
        log_line("Curved pull-over started: forward travel and outward steering, followed by braking.");return true;
    }
    bool both_stopped(speeding::Actor,speeding::Actor)const override{return paired_stop;}
    speeding::Actor spawn_officer(speeding::Actor police)override{
        if(!valid || !city || !owned_and_alive(police))return 0;
        auto manager=city->GetPedestrianManager();
        if(!manager){log_line("Scene cancelled: pedestrian manager unavailable.");return 0;}
        auto p=position(actor(police)),s=side();float offset=shoulder_offset*.5f+.45f;
        p.fX+=s.fX*offset;p.fZ+=s.fZ*offset;
        if(!ground_height(p,.02f)||!create(2,manager,0x410d,p,&heading))return 0;
        auto a=actor(3);a->SetVisible(false);a->SetOpacity(0,0);
        a->SetState(7,nullptr,-1,false,0,0,nullptr);a->SetSpeed(0,0);
        a->SetAutomataFlag(cISC4Automaton::AutomataFlagIgnoreAttractors,true);
        // Native pedestrian creation/idle setup can choose its own position.
        // Correct it while still invisible, and hold this same anchor during
        // the entire fade so walking cannot introduce a side-to-side jump.
        officer_position=p;officer_facing=heading;officer_turning=false;officer_turn_elapsed=0;
        a->PlayAnim(uint32_t(0x0c00));a->SetPosition(officer_position);a->SetOrientation(officer_facing);a->SetOpacity(0,0);a->SetVisible(true);
        log_line("Officer created at driver-side walk anchor.");return 3;
    }
    bool opacity(speeding::Actor a,float alpha)override{if(!owned_and_alive(a))return false;actor(a)->SetOpacity(alpha,0);return true;}
    bool walk_to_driver(speeding::Actor officer,speeding::Actor offender)override{
        target=position(actor(offender));auto s=side();float offset=shoulder_offset*.5f+.45f;
        target.fX+=s.fX*offset;target.fZ+=s.fZ*offset;
        if(!ground_height(target,.02f))return false;
        actor(officer)->SetPosition(officer_position);actor(officer)->PlayAnim(uint32_t(0));walking=true;officer_turning=false;log_line("Officer walking to driver.");return true;
    }
    bool at_driver(speeding::Actor,speeding::Actor)const override{return !walking && !officer_turning;}
    void clear_marker(){marker=false;}
    bool report_speeding(speeding::Actor offender,std::uint64_t& token)override{
        if(!valid)return false;
        auto p=position(actor(offender));int x=0,z=0;city->PositionToCell(p.fX,p.fZ,x,z);
        if(x<0||z<0)return false;
        marker_x=uint32_t(x);marker_z=uint32_t(z);marker=true;token=1;return true;
    }
    void retire_incident(std::uint64_t)override{} // Selection, not actor cleanup, retires the map marker.
    void remove_owned(speeding::Actor a)override{
        if(a<1||a>3)return;auto &o=actors[a-1];if(!o.ptr)return;
        auto ptr=o.ptr;if(a==2)set_lights(false);o={};
        if(valid){
            if(!ptr->CheckAutomataFlag(cISC4Automaton::AutomataFlagRemove)){
                ptr->SetState(7,nullptr,-1,false,0,0,nullptr);ptr->SetVisible(false);ptr->Remove(true);
            }
            if(a==2 && police_original_table){
                if(*reinterpret_cast<uintptr_t**>(ptr)==police_table_storage+1)
                    *reinterpret_cast<uintptr_t**>(ptr)=police_original_table;
                police_original_table=nullptr;
            }
            ptr->Release();
        }
    }
    bool update(float dt){
        if(!stopping && owned_and_alive(1) && owned_and_alive(2) && dt>0){
            drive_elapsed+=dt;float t=drive_elapsed>=1.5f?1:drive_elapsed/1.5f;
            float alpha=t*t*(3-2*t),travel=drive_speed*drive_elapsed;
            for(unsigned i=1;i<=2;++i){
                auto start=i==1?drive_offender:drive_police;
                if(!ground_pose(i,cS3DVector3(start.fX+heading.fX*travel,start.fY,start.fZ+heading.fZ*travel),heading))return false;
                actor(i)->SetOpacity(alpha,0);
            }
        }
        if(stopping && !paired_stop && owned_and_alive(1) && owned_and_alive(2) && dt>0){
            curve_elapsed+=dt;auto r=roadside();
            for(unsigned i=1;i<=2;++i){
                float delay=i==1?0:police_delay;
                auto start=i==1?curve_offender:curve_police;
                float before=curve_elapsed<delay?curve_elapsed:delay;
                float u=curve_elapsed<=delay?0:(curve_elapsed-delay)/3;if(u>1)u=1;
                float rest=1-u;
                // Both profiles start at drive_speed. The patrol follows .65s
                // later and brakes slightly harder to retain the final gap.
                float mix=i==1?0:.6333333333f;
                float forward=drive_speed*before+drive_speed*3*((1-mix)*(1-rest*rest)*.5f+mix*(1-rest*rest*rest)/3);
                float forward_tangent=curve_elapsed<delay?drive_speed*3:drive_speed*3*((1-mix)*rest+mix*rest*rest);
                float v=u/.7f;if(v>1)v=1;float rv=1-v;
                float lateral=v*v*v*v*(35+v*(-84+v*(70-20*v)));
                float lateral_tangent=u<.7f?140*v*v*v*rv*rv*rv/.7f:0;
                cS3DVector3 p(start.fX+heading.fX*forward+r.fX*shoulder_offset*lateral,start.fY,start.fZ+heading.fZ*forward+r.fZ*shoulder_offset*lateral);
                cS3DVector3 tangent(heading.fX*forward_tangent+r.fX*shoulder_offset*lateral_tangent,0,heading.fZ*forward_tangent+r.fZ*shoulder_offset*lateral_tangent);
                if(!ground_pose(i,p,u>=.7f?heading:normalized(tangent)))return false;
            }
            if(curve_elapsed>=3+police_delay){
                // Both final shoulder poses have been applied above. Keep
                // normal traffic collision handling until this exact point.
                // Candidate filter5059c0 excludes non-colliding cars, but
                // existing followers retain a cached leader until refreshed.
                actor(1)->SetAutomataFlag(cISC4Automaton::AutomataFlagCollide,false);
                actor(2)->SetAutomataFlag(cISC4Automaton::AutomataFlagCollide,false);
                // Native manager69 recomputes only followers whose cached
                // leader is this actor, with normal AddRef/Release handling.
                // Both flags must be cleared before either refresh.
                auto manager=actors[0].manager;
                auto table=*reinterpret_cast<uintptr_t**>(manager);
                auto refresh=reinterpret_cast<void(__thiscall*)(cISC4AutomataManager*,cISC4Automaton*)>(table[69]);
                refresh(manager,actor(1));refresh(manager,actor(2));
                paired_stop=true;
                log_line("Staggered shoulder stop complete; both cars grounded and aligned.");
                log_line("Parked scene collision disabled; cached traffic followers refreshed.");
            }
        }
        if(paired_stop && owned_and_alive(1) && owned_and_alive(2)){
            if(!ground_pose(1,position(actor(1)),heading)||!ground_pose(2,position(actor(2)),heading))return false;
        }
        if(owned_and_alive(3)){
            if(walking && dt>0){
                float d=distance(officer_position,target),step=dt*1.4f;
                if(d<=step){
                    officer_position=target;walking=false;actor(3)->PlayAnim(uint32_t(0x0c00));
                    if(!owned_and_alive(1))return false;
                    auto car=position(actor(1));officer_turn_target=normalized(cS3DVector3(car.fX-target.fX,0,car.fZ-target.fZ));
                    officer_turn_start=officer_facing;officer_turn_elapsed=0;officer_turning=true;
                    log_line("Officer reached door; turning to face parked car.");
                }else{
                    officer_facing=normalized(cS3DVector3(target.fX-officer_position.fX,0,target.fZ-officer_position.fZ));
                    officer_position.fX+=officer_facing.fX*step;officer_position.fZ+=officer_facing.fZ*step;
                }
            }
            if(officer_turning && dt>0){
                officer_turn_elapsed+=dt;float t=officer_turn_elapsed>=.4f?1:officer_turn_elapsed/.4f;
                float ease=t*t*(3-2*t);
                officer_facing=normalized(cS3DVector3(officer_turn_start.fX+(officer_turn_target.fX-officer_turn_start.fX)*ease,0,officer_turn_start.fZ+(officer_turn_target.fZ-officer_turn_start.fZ)*ease));
                if(t>=1)officer_turning=false;
            }
            if(!ground_height(officer_position,.02f))return false;
            actor(3)->SetPosition(officer_position);actor(3)->SetOrientation(officer_facing);
        }
        return true;
    }
};
static bool __fastcall incident_hook(cISC4CrimeSimulator* self,void*,EventVector& v){auto e=__atomic_load_n(&active_engine,__ATOMIC_ACQUIRE);return e?e->hooked_incidents(self,v):reinterpret_cast<IncidentFunction>(0x6a1960)(self,v);}

// No heap allocation or CRT initialization is needed for the permanent director.
inline void* operator new(__SIZE_TYPE__,void* p) noexcept{return p;}
void operator delete(void*) noexcept{}
void operator delete(void*,__SIZE_TYPE__) noexcept{}
static constexpr uint32_t DirectorID=0x9fd3c52b;
class Director final:public cIGZCOMDirector,public cIGZFrameWorkHooks,public cIGZMessageTarget2,public cIGZSystemService {
    cIGZCOM* com{};cIGZFrameWork* framework{};cISC4App* app{};
    cIGZMessageServer2* messages{};cIGZAllocatorService* alloc{};
    unsigned references=1;bool enabled=false,running=false,registered=false,prev_trigger=false;
    DWORD last_tick{},last_gap_log{};bool hidden_pause_logged=false,animation_blocked=false,ordinance_blocked=false,ordinance_menu_blocked=false;
    NativeEngine engine;// Allow the officer to cover the accepted trailing gap at walking speed.
    speeding::TrafficStop sequence{engine,{1.5,.5,12,1,30,2,1}};
    struct ConcurrentScene {
        NativeEngine engine;
        speeding::TrafficStop sequence{engine,{1.5,.5,12,1,30,2,1}};
    } additional[63];
    static constexpr unsigned SceneCount=64;
    NativeEngine& scene_engine(unsigned i){return i?additional[i-1].engine:engine;}
    speeding::TrafficStop& scene_sequence(unsigned i){return i?additional[i-1].sequence:sequence;}
    bool scene_busy(unsigned i){auto s=scene_sequence(i).stage();return s!=speeding::Stage::idle && s!=speeding::Stage::done && s!=speeding::Stage::aborted;}
    bool any_busy(){for(unsigned i=0;i<SceneCount;++i)if(scene_busy(i))return true;return false;}
    void clear_markers(){for(unsigned i=0;i<SceneCount;++i)scene_engine(i).clear_marker();}
    void cancel_scenes(){clear_markers();for(unsigned i=0;i<SceneCount;++i)scene_sequence(i).cancel();}
    cS3DVector3 pending[64]{};unsigned queue_head=0,queue_count=0;bool selection_pending=false;
    void detach(){queue_head=queue_count=0;selection_pending=false;cancel_scenes();for(unsigned i=SceneCount;i>0;--i)scene_engine(i-1).unbind();}
    void native_crime(cIGZMessage2* m){
        if(!enabled||!engine.city||GetCurrentThreadId()!=engine.thread)return;
        selection_pending=true;
        auto msg=static_cast<cIGZMessage2Standard*>(m);
        if(msg->GetData1()!=SpeedingID)return;
        if(!engine.speed_traps_available()||engine.speed_traps_on())return;
        auto object=msg->GetIGZUnknown();if(!object)return;
        void* lot=nullptr;
        if(!object->QueryInterface(0xe818fced,&lot)||!lot)return;
        auto table=*reinterpret_cast<uintptr_t**>(lot);cS3DVector3 p{};
        // Native lot GetCenter slot15 returns void despite the SDK bool label.
        reinterpret_cast<void(__thiscall*)(void*,cS3DVector3*)>(table[15])(lot,&p);
        reinterpret_cast<cIGZUnknown*>(lot)->Release();
        if(!__builtin_isfinite(p.fX)||!__builtin_isfinite(p.fZ))return;
        if(queue_count==64){log_line("Native Speeding event skipped: visual queue is full.");return;}
        pending[(queue_head+queue_count)%64]=p;++queue_count;
        log_line("Native monthly crime selection: Speeding visual queued near selected lot.");
    }
    void attach(){
        if(!enabled||!app)return;
        auto c=app->GetCity();if(!c || c==engine.city)return;
        if(engine.city)detach();engine.bind(c,alloc);
        for(unsigned i=1;i<SceneCount;++i){scene_engine(i).bind_scene(engine);scene_engine(i-1).next_scene=&scene_engine(i);}
        scene_engine(SceneCount-1).next_scene=nullptr;
        queue_head=queue_count=0;selection_pending=false;last_tick=GetTickCount();
    }
public:
    bool QueryInterface(uint32_t id,void** out)override{
        if(!out)return false;*out=nullptr;
        if(id==1||id==0xa21ee941||id==DirectorID)*out=static_cast<cIGZCOMDirector*>(this);
        else if(id==0x03fa40bf)*out=static_cast<cIGZFrameWorkHooks*>(this);
        else if(id==0x287fb697)*out=static_cast<cIGZSystemService*>(this);
        else if(id==0x452294aa)*out=static_cast<cIGZMessageTarget2*>(this);
        if(*out){AddRef();return true;}return false;
    }
    uint32_t AddRef()override{return ++references;}
    uint32_t Release()override{if(references>1)--references;return references;}
    uint32_t RemoveRef()override{return Release();}
    uint32_t RefCount()override{return references;}
    bool InitializeCOM(cIGZCOM* c,const cIGZString&)override{com=c;framework=c->FrameWork();return true;}
    bool OnStart(cIGZCOM*)override{if(framework)framework->AddHook(static_cast<cIGZFrameWorkHooks*>(this));return true;}
    void EnumClassObjects(ClassObjectEnumerationCallback,void*)override{}
    bool GetClassObject(uint32_t,uint32_t,void** p)override{if(p)*p=nullptr;return false;}
    bool CanUnloadNow()override{return false;}
    bool OnUnload()override{return true;}
    cIGZFrameWork* FrameWork()override{return framework;}
    cIGZCOM* GZCOM()override{return com;}
    void AddDirector(cIGZCOMDirector*)override{}
    bool GetLibraryPath(cIGZString& p)override{char path[512]{};GetModuleFileNameA(module,path,511);p.FromChar(path);return true;}
    uint32_t GetHeapAllocatedSize()override{return 0;}
    bool PreFrameWorkInit()override{return true;}
    bool PreAppInit()override{return true;}
    bool PostAppInit()override{
        paths();log_line("SC4Speeding 0.58 experimental native DLL loaded; in-game behavior unverified.");
        if(!supported()){log_line("Disabled: executable or native signatures unsupported.");return true;}
        if(!framework || !framework->Application() || !framework->Application()->QueryInterface(0x26ce01c0,reinterpret_cast<void**>(&app)))return true;
        if(!framework->GetSystemService(83526747,1696765127,reinterpret_cast<void**>(&messages)) || !messages){log_line("Disabled: message service unavailable.");return true;}
        if(!framework->GetSystemService(988069539,988069547,reinterpret_cast<void**>(&alloc)) || !alloc){log_line("Disabled: allocator service unavailable.");return true;}
        const uint32_t notices[]={0xea8ae29a,0x26d31ec2,0x0a159d95,0x88ea4dff};
        for(auto id:notices)if(!messages->AddNotification(static_cast<cIGZMessageTarget2*>(this),id)){log_line("Disabled: lifecycle subscription failed.");return true;}
        enabled=GetPrivateProfileIntA("Speeding","Enabled",1,ini_path)!=0;
        registered=framework->AddToTick(static_cast<cIGZSystemService*>(this));
        running=registered;enabled=enabled&&registered;last_tick=GetTickCount();
        log_line(enabled?"Ready. Native monthly crime selection active (weight4); Ctrl+Shift+F10 requests a test scene.":"Disabled by configuration or tick registration failure.");
        return true;
    }
    bool PreAppShutdown()override{
        enabled=false;if(engine.city)detach();
        if(registered&&framework)framework->RemoveFromTick(static_cast<cIGZSystemService*>(this));registered=false;running=false;
        if(messages){messages->RemoveNotification(static_cast<cIGZMessageTarget2*>(this),0x88ea4dff);messages->RemoveNotification(static_cast<cIGZMessageTarget2*>(this),0x0a159d95);messages->RemoveNotification(static_cast<cIGZMessageTarget2*>(this),0xea8ae29a);messages->RemoveNotification(static_cast<cIGZMessageTarget2*>(this),0x26d31ec2);messages->Release();messages=nullptr;}
        if(alloc){alloc->Release();alloc=nullptr;}if(app){app->Release();app=nullptr;}
        return true;
    }
    bool PostAppShutdown()override{return true;}
    bool PostSystemServiceShutdown()override{return true;}
    bool AbortiveQuit()override{return true;}
    bool OnInstall()override{return true;}
    bool DoMessage(cIGZMessage2* m)override{
        if(m->GetType()==0x26d31ec2){if(engine.city)detach();}
        else if(m->GetType()==0xea8ae29a)attach();
        else if(m->GetType()==0x0a159d95)native_crime(m);
        else if(m->GetType()==0x88ea4dff && enabled && engine.city && GetCurrentThreadId()==engine.thread){
            clear_markers();selection_pending=false;
        }
        return true;
    }
    uint32_t GetServiceID()override{return DirectorID;}
    cIGZSystemService* SetServiceID(uint32_t)override{return this;}
    int32_t GetServicePriority()override{return 200;}
    bool IsServiceRunning()override{return running;}
    cIGZSystemService* SetServiceRunning(bool b)override{running=b;return this;}
    bool Init()override{return true;}
    bool Shutdown()override{return PreAppShutdown();}
    bool OnTick(uint32_t)override{
        DWORD now=GetTickCount();float dt=float(DWORD(now-last_tick))*.001f;last_tick=now;
        if(dt>1.0f)dt=1.0f; // Bounded catch-up instead of discarding every gap above250ms.
        if(!enabled||!app||!engine.city)return true;
        if(app->GetCity()!=engine.city){for(unsigned i=0;i<SceneCount;++i)scene_engine(i).context_lost();cancel_scenes();queue_head=queue_count=0;selection_pending=false;return true;}
        maintain_crime_panel(app);
        bool busy=any_busy();
        engine.make_speed_traps_available();
        engine.set_selection_enabled(engine.speed_traps_available()&&!engine.speed_traps_on());
        if(!engine.speed_traps_available()){
            cancel_scenes();queue_head=queue_count=0;
            if(!ordinance_menu_blocked)log_line("Speeding suppressed: Speed Traps is not available in the ordinance menu.");
            ordinance_menu_blocked=true;return true;
        }
        if(ordinance_menu_blocked){ordinance_menu_blocked=false;log_line("Speed Traps is available in the ordinance menu; eligible speeding scenes enabled.");}
        // Ordinance suppression also applies to manual hotkey requests and an
        // already active scene; no separate budget or saved-state handling.
        if(engine.speed_traps_on()){
            cancel_scenes();
            if(!ordinance_blocked)log_line("Speed Traps active: speeding scenes suppressed.");
            ordinance_blocked=true;queue_head=queue_count=0;return true;
        }
        if(ordinance_blocked){ordinance_blocked=false;log_line("Speed Traps repealed: speeding scenes enabled.");}
        auto sim=engine.city->GetSimulator();if(!sim)return true;
        // Hidden pauses suspend simulation agents; this scene uses only its
        // own scripted actors. Continue it while the game still supplies ticks.
        // Never start a new scene while any pause is active.
        if(modal_ui_open(app)||sim->IsPaused()||sim->IsEmergencyPaused()||(!busy&&sim->IsAnyPaused())){
            animation_blocked=true;return true;
        }
        // Consume the resume tick as a new clock baseline. Menu time must
        // never become catch-up motion, including when modal ticks are sparse.
        if(animation_blocked){animation_blocked=false;return true;}
        float scale=sim->GetAnimationTimeDilation();
        if(!__builtin_isfinite(scale)||scale<=0)return true;
        dt*=scale;if(dt>4)dt=4;
        if(busy&&sim->IsHiddenPaused()&&!hidden_pause_logged){hidden_pause_logged=true;log_line("Animation timing: continuing active scene through a hidden simulation pause.");}
        if(busy&&dt>.5f&&(!last_gap_log||DWORD(now-last_gap_log)>5000)){last_gap_log=now;log_line("Animation timing: game update gap exceeded 500 ms; applying bounded catch-up.");}
        #if SC4_SPEEDING_DEBUG
        bool trigger=(GetAsyncKeyState(0x11)<0 && GetAsyncKeyState(0x10)<0 && GetAsyncKeyState(0x79)<0);
        bool edge=trigger&&!prev_trigger;prev_trigger=trigger;
        #else
        constexpr bool edge=false;
        #endif
        if(busy && edge){
            cancel_scenes();busy=false;
            log_line("Hotkey restart: previous pullover actors and marker removed; starting a new sequence.");
        }
        if(edge){
            // Manual testing still replaces all owned scenes, rather than accumulating them.
            cancel_scenes();queue_head=queue_count=0;engine.request_near(nullptr);
            if(!sequence.start())log_line("Speeding scene skipped: no eligible site or vehicle support.");
            else engine.focus_scene();
        }
        // Assign each new native incident an independent actor/animation state.
        // Never wait for an existing scene's officer/fades to finish.
        if(!selection_pending){
            for(unsigned i=0;i<SceneCount && queue_count;++i){
                if(scene_busy(i))continue;
                auto center=pending[queue_head];queue_head=(queue_head+1)%64;--queue_count;
                scene_engine(i).request_near(&center);
                if(!scene_sequence(i).start())log_line("Speeding scene skipped: no eligible site or vehicle support.");
            }
        }
        for(unsigned i=0;i<SceneCount;++i){
            if(!scene_busy(i))continue;
            auto& e=scene_engine(i);auto& q=scene_sequence(i);float remaining=dt;
            while(remaining>0){
                float step=remaining>.25f?.25f:remaining;
                if(e.update(step))q.tick(step);else {e.clear_marker();q.cancel();break;}
                remaining-=step;
            }
            auto end=q.stage();
            if(end==speeding::Stage::done)log_line("Traffic stop completed; actors removed; marker retained until next crime selection.");
            else if(end==speeding::Stage::aborted){e.clear_marker();log_line("Traffic stop aborted; owned actors and marker cleaned up.");}
        }
        return true;
    }
    // Idle callbacks must not consume elapsed time before the next active tick.
    // OnTick owns the clock baseline, including explicit simulation pauses.
    bool OnIdle(uint32_t)override{return true;}
    int32_t GetServiceTickPriority()override{return 200;}
};
static bool initialized;
alignas(Director) static unsigned char director_storage[sizeof(Director)];
extern "C" __declspec(dllexport) cIGZCOMDirector* __cdecl GZDllGetGZCOMDirector(){
    paths();log_line("GZDllGetGZCOMDirector: game requested plugin director.");
    if(!initialized){new(director_storage)Director();initialized=true;}
    return static_cast<Director*>(static_cast<void*>(director_storage));
}
extern "C" BOOL __stdcall DllMain(void* h,DWORD reason,void*){if(reason==1){module=h;DisableThreadLibraryCalls(h);}return 1;}
extern "C" void* memcpy(void* d,const void* s,__SIZE_TYPE__ n){auto a=static_cast<unsigned char*>(d);auto b=static_cast<const unsigned char*>(s);for(__SIZE_TYPE__ i=0;i<n;++i)a[i]=b[i];return d;}
extern "C" void* memset(void* d,int v,__SIZE_TYPE__ n){auto a=static_cast<unsigned char*>(d);for(__SIZE_TYPE__ i=0;i<n;++i)a[i]=static_cast<unsigned char>(v);return d;}
extern "C" int _purecall(){return 0;}

extern "C" { int _fltused=0; }
