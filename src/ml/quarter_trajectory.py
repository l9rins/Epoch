import numpy as np
from sklearn.linear_model import LinearRegression

class QuarterTrajectory:
    def __init__(self):
        self.home_model = LinearRegression()
        self.away_model = LinearRegression()
        
    def analyze(self, state, previous_states) -> dict:
        curr_q = state["quarter"]
        
        # Filter to only states in this quarter
        q_states = [s for s in previous_states if s["quarter"] == curr_q]
        q_states.append(state)
        
        if len(q_states) < 10:
            return {"home_q_projection": 0, "away_q_projection": 0, "trajectory": "INSUFFICIENT_DATA", "confidence": 0.0}
            
        times = []
        home_pts = []
        away_pts = []
        
        start_home = q_states[0]["home_score"]
        start_away = q_states[0]["away_score"]
        
        for s in q_states:
            # seconds elapsed in quarter
            q_time = 720 - (s["time_remaining"] % 720) 
            if s["quarter"] > 4: # OT
                q_time = 300 - (s["time_remaining"] % 300)
                
            times.append([q_time])
            home_pts.append(s["home_score"] - start_home)
            away_pts.append(s["away_score"] - start_away)
            
        X = np.array(times)
        
        self.home_model.fit(X, home_pts)
        self.away_model.fit(X, away_pts)
        
        q_len = 720 if curr_q <= 4 else 300
        proj_home = self.home_model.predict([[q_len]])[0]
        proj_away = self.away_model.predict([[q_len]])[0]
        
        h_rate = self.home_model.coef_[0] * 60
        a_rate = self.away_model.coef_[0] * 60
        
        if h_rate > a_rate + 0.02:
            traj = "HOME_ACCELERATING"
        elif a_rate > h_rate + 0.02:
            traj = "AWAY_ACCELERATING"
        elif h_rate < 0.01 and a_rate < 0.01:
            traj = "DEFENSIVE_LOCKDOWN"
        else:
            traj = "STABLE"
            
        return {
            "home_q_projection": int(proj_home + start_home),
            "away_q_projection": int(proj_away + start_away),
            "trajectory": traj,
            "confidence": min(1.0, len(q_states) / 50.0) # More samples = higher conf
        }

if __name__ == "__main__":
    qt = QuarterTrajectory()
    sample_states = []
    base_t = 2880
    for i in range(15):
        sample_states.append({
            "quarter": 1, "time_remaining": base_t - (i * 10), 
            "home_score": i * 2, "away_score": i * 1
        })
        
    res = qt.analyze(sample_states[-1], sample_states[:-1])
    print(f"Sample Trajectory: {res}")
