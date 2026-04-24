import { useMutation } from "@tanstack/react-query";
import axios from "axios";
import { useState } from "react";
import useAuthContext from "./AuthContext";
import Svg from "./Svg";
import PropTypes from "prop-types";

Vote.propTypes = {
  url: PropTypes.string,
  initialCount: PropTypes.number,
  intitalVote: PropTypes.bool,
  contentID: PropTypes.number,
  type: PropTypes.string,
};

export default function Vote({ url, intitalVote, initialCount, contentID, type }) {
  const [vote, setVote] = useState(intitalVote);
  const [voteCount, setVoteCount] = useState(initialCount);
  const { isAuthenticated } = useAuthContext();

  const { mutate, isPending } = useMutation({
    mutationFn: async ({ vote: newVote, method, contentID }) => {
      switch (method) {
        case "put":
          return axios
            .put(`${url}/${contentID}`, { is_upvote: newVote })
            .then((res) => res.data);
        case "patch":
          return axios
            .patch(`${url}/${contentID}`, { is_upvote: newVote })
            .then((res) => res.data);
        case "delete":
          return axios.delete(`${url}/${contentID}`).then((res) => res.data);
        default:
          break;
      }
    },
    onSuccess: (data, variables) => {
      const { vote: newVote } = variables;
      if (data.current_vote !== undefined) {
        setVote(data.current_vote);
      } else {
        setVote(newVote);
      }
      if (data.vote_delta !== undefined) {
        setVoteCount((prev) => prev + data.vote_delta);
      }
    },
    onError: (error) => {
      console.error("Vote failed:", error);
      alert(error.response?.data?.message || "Vote failed. Please try again.");
    },
  });

  function handleVote(newVote) {
    if (!isAuthenticated) {
      return alert("You must be logged in to vote.");
    }

    if (isPending) {
      return;
    }

    let method;
    if (vote === null) {
      method = "put";
    } else if (newVote === null) {
      method = "delete";
    } else {
      method = "patch";
    }

    mutate({ vote: newVote, method, contentID });
  }

  return type === "mobile" ? (
    <>
      <Svg
        type="mobileVote"
        className={`w-5 h-5 md:w-6 md:h-6 ${isPending ? "opacity-50" : ""}`}
        defaultStyle={true}
        active={vote === true}
        onClick={() => handleVote(!vote ? true : null)}
      />
      <p
        className={`${vote === true ? "text-theme-red-coral" : vote === false ? "text-sky-600" : ""} ${
          isPending ? "opacity-50" : ""
        }`}
      >
        {voteCount}
      </p>
      <Svg
        type="mobileVote"
        className={`w-5 h-5 rotate-180 md:w-6 md:h-6 ${isPending ? "opacity-50" : ""}`}
        defaultStyle={false}
        active={vote === false}
        onClick={() => handleVote(vote === false ? null : false)}
      />
    </>
  ) : (
    <>
      <div
        className={`px-5 py-0.5 bg-orange-100 rounded-md ${isPending ? "opacity-50" : ""}`}
      >
        <Svg
          type="down-arrow"
          defaultStyle={true}
          className="w-10 h-10 rotate-180"
          onClick={() => handleVote(!vote ? true : null)}
          active={vote === true}
        />
      </div>
      <p className="text-lg font-semibold">
        <span
          className={`${vote === true ? "text-theme-red-coral" : vote === false ? "text-sky-600" : ""} ${
            isPending ? "opacity-50" : ""
          }`}
        >
          {voteCount}
        </span>
      </p>
      <div
        className={`px-5 py-0.5 bg-blue-50 rounded-md group ${isPending ? "opacity-50" : ""}`}
      >
        <Svg
          type="down-arrow"
          className="w-10 h-10"
          defaultStyle={false}
          onClick={() => handleVote(vote === false ? null : false)}
          active={vote === false}
        />
      </div>
    </>
  );
}
